import { useState, useEffect } from "react";
import { Box, Stack, Center, Heading, SimpleGrid, GridItem } from "@chakra-ui/react";
import { getAllCategories, getTransactions } from "../api/endpoints";
import { getToken } from "../lib/auth";
import { SpinnerLoading } from "../components/spinnerLoading";
import CategoryPieChart from "../components/CategoryPieChart";
import ExpenseTrendLine from "../components/ExpenseTrendLine";
import TopCategoriesBarList from "../components/TopCategoriesBarList";

export default function Dashboard() {
    const [loading, setLoading] = useState(true);
    const [categories, setCategories] = useState([]);
    const [transactions, setTransactions] = useState([]);

    useEffect(() => {
        const token = getToken();
        // Request all transactions by passing null date filters
        const allTransactionsQuery = { organized_by: null, date: null };

        Promise.all([
            getAllCategories(token),
            getTransactions(allTransactionsQuery, token)
        ]).then(([categoriesData, transactionsData]) => {
            if (categoriesData) {
                setCategories(categoriesData.data);
            } 
            if (transactionsData) {
                setTransactions(transactionsData.data);
            }
            setLoading(false);
        }).catch(err => {
            console.error(err);
            setLoading(false);
        });
    }, []);

    return (
        <Center>
            <Stack
                minHeight="100vh"
                gap={6}
                w="full"
                maxW="6xl"
                align="center"
                justify="flex-start"
                py={10}
                px={4}
            >   
                <Heading size="2xl" mb={6}>
                    Dashboard
                </Heading>
                
                {loading ? (
                    <SpinnerLoading />
                ) : (
                    <SimpleGrid columns={{ base: 1, lg: 2 }} gap={6} w="full">
                        <GridItem colSpan={{ base: 1, lg: 2 }}>
                            <ExpenseTrendLine transactions={transactions} />
                        </GridItem>
                        <GridItem>
                            <CategoryPieChart transactions={transactions} categories={categories} />
                        </GridItem>
                        <GridItem>
                            <TopCategoriesBarList transactions={transactions} categories={categories} />
                        </GridItem>
                    </SimpleGrid>
                )}
            </Stack>
        </Center>
    );
}