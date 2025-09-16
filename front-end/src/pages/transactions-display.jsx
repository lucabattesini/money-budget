import { useState, useEffect } from "react";
import { Center, Stack, Heading, Card, Flex, Text, IconButton, Box } from "@chakra-ui/react";
import { getTransactions, getAllCategories } from "../api/endpoints";
import { SpinnerLoading } from "../components/spinnerLoading";
import { IoIosCloseCircle } from "react-icons/io";
import { deleteTransaction } from "../api/endpoints";

export default function TransactionsDisplay() {
    const [loading, setLoading] = useState(true)
    const [categories, setCategories] = useState([])
    const [transactions, setTransactions] = useState([]);
    const [trigger, setTrigger] = useState(0);

    useEffect(() => {
        Promise.all([
            getAllCategories(),
            getTransactions({"organized_by": "all", "date": null})
        ]).then(([categoriesData, transactionsData]) => {
            if (categoriesData && transactionsData) {
                setCategories(categoriesData.data)
                setTransactions(transactionsData.data)
                setLoading(false)
            }
        })
    }, [trigger]);


    const onDelete = (id) => {
        deleteTransaction(id);
        setTrigger(trigger + 1);
    }

    return(
        <Center>
            <Stack
                height="100vh"
                gap={6}
                width="35vh"
                align="center"
                justify="flex-start"
                pt={20}
            >
                <Heading size={"2xl"}>
                    Transactions list
                </Heading>
                
                {loading && <SpinnerLoading/>}
                {!loading && transactions.map((transaction) => {
                    const categoryObj = categories?.find((category) => String(category.id) === transaction.category);
                    const categoryName = categoryObj ? categoryObj.name : "Category not found";
                    const formatedDate = new Date(transaction.date)
                     
                    return (
                        <Card.Root 
                        
                        width={"300px"} 
                        height={"150px"}
                        key={transaction.id}
                        >
                            <Box alignSelf={"end"} marginRight={"5px"}>
                                <IconButton 
                                variant="ghost" 
                                color="white" 
                                size="1px"
                                onClick={() => onDelete(transaction.id)}>
                                    <IoIosCloseCircle size="1.5vh"/>
                                </IconButton>
                            </Box>

                            <Card.Header
                            paddingTop={"0.5vh"}>
                                <Flex justify="space-between">
                                    <Text>
                                        - {transaction.value /100} R$
                                    </Text>
                                    <Text>
                                        {categoryName}
                                    </Text>
                                </Flex>
                            </Card.Header>
                            <Card.Body
                            color="fg.muted"
                            >
                                <Flex
                                justify="space-between">
                                    <Text
                                    whiteSpace="normal"
                                    wordBreak="break-word"
                                    maxW="15ch">
                                        {transaction.label}
                                    </Text>
                                    <Text>
                                        {formatedDate.toLocaleDateString("pt-BR")}
                                    </Text>
                                </Flex>
                            </Card.Body>
                        </Card.Root>
                    )
            })}
            </Stack>
        </Center>
    )
}