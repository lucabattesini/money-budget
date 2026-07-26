import { useState, useEffect } from "react";
import { Center, Stack, Heading, Card, Flex, Text, IconButton, Box, Separator } from "@chakra-ui/react";
import { getTransactions, getAllCategories, deleteTransaction } from "../api/endpoints";
import { getToken } from "../lib/auth";
import { SpinnerLoading } from "../components/spinnerLoading";
import TransactionSummary from "../components/TransactionSummary";
import { IoIosCloseCircle } from "react-icons/io";

export default function TransactionsDisplay() {
    const [loading, setLoading] = useState(true);
    const [categories, setCategories] = useState([]);
    const [transactions, setTransactions] = useState([]);
    const [trigger, setTrigger] = useState(0);

    useEffect(() => {
        const token = getToken();
        Promise.all([
            getAllCategories(token),
            getTransactions({"organized_by": null, "date": null}, token)
        ]).then(([categoriesData, transactionsData]) => {
            if (categoriesData) setCategories(categoriesData.data);
            if (transactionsData) setTransactions(transactionsData.data);
            setLoading(false);
        });
    }, [trigger]);

    const onDelete = (id) => {
        deleteTransaction(id, getToken());
        setTrigger(trigger + 1);
    }

    const today = [];
    const thisWeek = [];
    const thisMonth = [];
    const older = [];

    const now = new Date();
    // Start of today
    const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    
    // Start of this week (last 7 days)
    const startOfWeek = new Date(startOfToday);
    startOfWeek.setDate(startOfWeek.getDate() - 7);

    // Start of this month
    const startOfMonth = new Date(now.getFullYear(), now.getMonth(), 1);

    transactions.forEach(transaction => {
        const tDate = new Date(transaction.date);
        if (tDate >= startOfToday) {
            today.push(transaction);
        } else if (tDate >= startOfWeek) {
            thisWeek.push(transaction);
        } else if (tDate >= startOfMonth) {
            thisMonth.push(transaction);
        } else {
            older.push(transaction);
        }
    });

    const groups = [
        { title: "Hoje", data: today },
        { title: "Esta Semana", data: thisWeek },
        { title: "Este Mês", data: thisMonth },
        { title: "Todo o Resto", data: older },
    ];

    const renderTransactionCard = (transaction) => {
        const categoryObj = categories?.find((category) => String(category.id) === transaction.category);
        const categoryName = categoryObj ? categoryObj.name : "Categoria não encontrada";
        const formatedDate = new Date(transaction.date);

        return (
            <Card.Root width="300px" height="150px" key={transaction.id} mb={4}>
                <Box alignSelf="end" marginRight="5px">
                    <IconButton variant="ghost" color="white" size="1px" onClick={() => onDelete(transaction.id)}>
                        <IoIosCloseCircle size="1.5vh"/>
                    </IconButton>
                </Box>
                <Card.Header paddingTop="0.5vh">
                    <Flex justify="space-between">
                        <Text>- {transaction.value /100} R$</Text>
                        <Text>{categoryName}</Text>
                    </Flex>
                </Card.Header>
                <Card.Body color="fg.muted">
                    <Flex justify="space-between">
                        <Text whiteSpace="normal" wordBreak="break-word" maxW="15ch">
                            {transaction.label}
                        </Text>
                        <Text>
                            {formatedDate.toLocaleDateString("pt-BR")}
                        </Text>
                    </Flex>
                </Card.Body>
            </Card.Root>
        );
    }

    return(
        <Center>
            <Stack minHeight="100vh" gap={6} w="full" maxW="md" align="center" justify="flex-start" py={10}>
                <TransactionSummary transactions={transactions} />

                {loading && <SpinnerLoading/>}
                
                {!loading && groups.map(group => {
                    if (group.data.length === 0) return null;
                    return (
                        <Box key={group.title} w="full" display="flex" flexDirection="column" alignItems="center">
                            <Flex w="full" align="center" mb={6} mt={2}>
                                <Box color="gray.400" mr={4} fontSize="xs" fontWeight="bold" textTransform="uppercase">
                                    {group.title}
                                </Box>
                                <Separator flex="1" borderColor="gray.700" />
                            </Flex>
                            
                            {group.data.map(renderTransactionCard)}
                        </Box>
                    );
                })}
            </Stack>
        </Center>
    )
}