import { useState, useEffect } from "react";
import { Center, Stack, Heading, Card, Text, Flex } from "@chakra-ui/react";

export default function TransactionsDisplay() {
    const [categories, setCategories] = useState([])
    const [transactions, setTransactions] = useState([]);

    useEffect(() => {
        fetch("http://127.0.0.1:8000/report-expense/", {
            method: "get"
        })
            .then(Response => Response.json())
            .then(data => setTransactions(data.data))

            .catch(error => console.error("Failed to get transactions", error))
    }, []);

    useEffect(() => {
        fetch("http://127.0.0.1:8000/categories/", {
            method: "get"
        })
            .then(Response => Response.json())
            .then(data => setCategories(data.data))

            .catch(error => console.error("Failed to get categories", error))
    }, [])

    return(
        <Center>
            <Stack
                height="100vh"
                gap={6}
                width="35vh"
                align="center"
                justify="center"
            >
                <Heading>
                    Transactions list
                </Heading>

                {transactions?.map((item) => {
                    const category = categories.find((obj) => obj.id === item.id);
                    const categoryName = category ? category.name : "Category not found";

                    return (
                        <Card.Root size="sm" width={"35vh"} key={item.id}>
                          <Card.Header>
                            <Flex justify="space-between">
                                <Text>{item.value / 100}</Text>
                                <Text>{categoryName}</Text>
                            </Flex>
                          </Card.Header>
                          <Card.Body color="fg.muted">
                            {item.label}
                          </Card.Body>
                        </Card.Root>
                    )
                })}

            </Stack>
        </Center>
    )
}