import { useState, useEffect } from "react";
import { Center, Stack, Heading, Box, Table } from "@chakra-ui/react";
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

                <Table.Root>
                    <Table.Header>
                        <Table.Row>
                            <Table.ColumnHeader>Description</Table.ColumnHeader>
                            <Table.ColumnHeader>Amount</Table.ColumnHeader>
                            <Table.ColumnHeader display={{ base: "none", md: "table-cell" }}>Category</Table.ColumnHeader>
                            <Table.ColumnHeader>Date</Table.ColumnHeader>
                        </Table.Row>
                    </Table.Header>
                    <Table.Body>
                        {transactions.map((transaction) => {
                            const categoryObj = categories.find((category) => String(category.id) === transaction.category);
                            const categoryName = categoryObj ? categoryObj.name : "Category not found";
                            const formatedDate = new Date(transaction.date)
                             
                            return (
                                <Table.Row key={transaction.id}>
                                    <Table.Cell>{transaction.label}</Table.Cell>
                                    <Table.Cell>-{transaction.value / 100}&nbsp;R$</Table.Cell>
                                    <Table.Cell display={{ base: "none", md: "table-cell" }}>{categoryName}</Table.Cell>
                                    <Table.Cell>{formatedDate.toLocaleDateString("pt-BR")}</Table.Cell>
                                </Table.Row>
                            )
                        })}
                    </Table.Body>
                </Table.Root>
            </Stack>
        </Center>
    )
}