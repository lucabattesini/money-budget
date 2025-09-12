import { useState, useEffect } from "react";
import { Center, Stack, Heading, Box, Card, Flex, Text } from "@chakra-ui/react";
import { getAllTransactions, getAllCategories } from "../api/endpoints";
import { SpinnerLoading } from "../components/spinnerLoading";

export default function TransactionsDisplay() {
    const [loading, setLoading] = useState(true)
    const [categories, setCategories] = useState([])
    const [transactions, setTransactions] = useState([]);

    useEffect(() => {
        Promise.all([
            getAllCategories(),
            getAllTransactions()
        ]).then(([categoriesData, transactionsData]) => {
            if (categoriesData && transactionsData) {
                setCategories(categoriesData.data)
                setTransactions(transactionsData.data)
                setLoading(false)
            }
        })
    }, []);

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
                        size="sm"
                        width={"35vh"} 
                        height={"14vh"}
                        key={transaction.id}
                        >
                            <Card.Header>
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