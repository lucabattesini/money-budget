import { useState, useEffect } from "react";
import { Center, Stack, Heading, Box, Card, Flex, Text } from "@chakra-ui/react";
import { getAllTransactions, getAllCategories } from "../api/endpoints";
import Home from "./home";

export default function TransactionsDisplay() {
    const [categories, setCategories] = useState([])
    const [transactions, setTransactions] = useState([]);

    useEffect(() => {
            getAllTransactions().then(data => setTransactions(data.data.slice().reverse()))
    }, []);

    useEffect(() => {
        getAllCategories().then(data => {
            if (data) {
                setCategories(data.data)
            }
        })
    }, [])

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
                <Box position="absolute" right={6} top={6}>
                    <Home/>
                </Box>

                <Heading size={"2xl"}>
                    Transactions list
                </Heading>

                {transactions.map((transaction) => {
                    const categoryObj = categories.find((category) => String(category.id) === transaction.category);
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