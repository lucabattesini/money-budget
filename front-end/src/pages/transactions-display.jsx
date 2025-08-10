import { useState, useEffect } from "react";
import { Center, Stack, Heading, Card, Text, Flex } from "@chakra-ui/react";
import { getAllTransactions, getAllCategories } from "../api/endpoints";

export default function TransactionsDisplay() {
    const [categories, setCategories] = useState([])
    const [transactions, setTransactions] = useState([]);

    useEffect(() => {
            getAllTransactions().then(data => setTransactions(data.data))
    }, []);

    useEffect(() => {
            getAllCategories().then(data => setCategories(data.data))
    }, [])

    return(
        <Center>
            <Stack
                height="100vh"
                gap={6}
                width="35vh"
                align="center"
                justify="flex-start"
                pt={16}
            >
                <Heading size={"2xl"}>
                    Transactions list
                </Heading>

                {transactions.map((transaction) => {
                    const categoryObj = categories.find((category) => String(category.id) === transaction.category);
                    const categoryName = categoryObj ? categoryObj.name : "Category not found";

                    return (
                        <Card.Root size="sm" width={"35vh"} key={transaction.id}>
                          <Card.Header>
                            <Flex justify="space-between">
                                <Text>{transaction.value / 100}</Text>
                                <Text>{categoryName}</Text>
                            </Flex>
                          </Card.Header>
                          <Card.Body color="fg.muted">
                            {transaction.label}
                          </Card.Body>
                        </Card.Root>
                    )
                })}

            </Stack>
        </Center>
    )
}