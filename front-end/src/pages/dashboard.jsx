import { useState, useEffect } from "react";
import { Box, Stack, Center, Heading, SimpleGrid, GridItem } from "@chakra-ui/react";
import { getAllCategories, getTransactions, getMe } from "../api/endpoints";
import { getToken } from "../lib/auth";
import { SpinnerLoading } from "../components/spinnerLoading";
import CategoryPieChart from "../components/CategoryPieChart";
import ExpenseTrendLine from "../components/ExpenseTrendLine";
import TopCategoriesBarList from "../components/TopCategoriesBarList";

export default function Dashboard() {
    const [loading, setLoading] = useState(true);
    const [categories, setCategories] = useState([]);
    const [transactions, setTransactions] = useState([]);
    const [user, setUser] = useState(null);

    useEffect(() => {
        const token = getToken();
        // Request all transactions by passing null date filters
        const allTransactionsQuery = { organized_by: null, date: null };

        Promise.all([
            getAllCategories(token),
            getTransactions(allTransactionsQuery, token),
            getMe(token)
        ]).then(([categoriesData, transactionsData, userData]) => {
            if (categoriesData) {
                setCategories(categoriesData.data);
            }
            if (transactionsData) {
                setTransactions(transactionsData.data);
            }
            if (userData?.data) {
                setUser(userData.data);
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
                {user && (
                    <Heading
                        size="2xl"
                        mb={6}
                        w="full"
                        textAlign="left"
                        bgGradient="linear(to-r, teal.400, blue.500)"
                        bgClip="text"
                        fontWeight="extrabold"
                    >
                        Welcome back, {user.name.split(' ')[0]} 👋
                    </Heading>
                )}
                {loading ? (
                    <SpinnerLoading />
                ) : (
                    <SimpleGrid columns={{ base: 1, lg: 2 }} gap={6} w="full">
                        <GridItem>
                            <CategoryPieChart transactions={transactions} categories={categories} />
                        </GridItem>
                        <GridItem>
                            <TopCategoriesBarList transactions={transactions} categories={categories} />
                        </GridItem>
                        <GridItem colSpan={{ base: 1, lg: 2 }}>
                            <ExpenseTrendLine transactions={transactions} />
                        </GridItem>
                    </SimpleGrid>
                )}
            </Stack>
        </Center>
    );
}