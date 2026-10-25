import { useState, useEffect } from "react";
import { Box, Stack, Center, Heading, SimpleGrid, GridItem, Text, Flex } from "@chakra-ui/react";
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

    const now = new Date();
    const monthTotal = transactions
        .filter(t => {
            const tDate = new Date(t.date);
            return tDate.getFullYear() === now.getFullYear() && tDate.getMonth() === now.getMonth();
        })
        .reduce((sum, t) => sum + t.value / 100, 0);
    const monthName = now.toLocaleDateString('pt-BR', { month: 'long' });
    const formattedMonthTotal = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(monthTotal);

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
                        Bem-vindo de volta, {user.name.split(' ')[0]} 👋
                    </Heading>
                )}
                {loading ? (
                    <SpinnerLoading />
                ) : (
                    <>
                    <Flex w="full" justify="center" py={{ base: 6, md: 10 }} mb={4}>
                        {/* Shrink-wrapped box: centered on the page, label aligned to the value's left edge */}
                        <Box textAlign="left">
                            <Text fontSize={{ base: "xs", md: "sm" }} color="gray.400" textTransform="uppercase" letterSpacing="0.3em" fontWeight="medium" mb={3}>
                                Gastos de {monthName}
                            </Text>
                            <Text fontSize={{ base: "5xl", sm: "6xl", md: "8xl", lg: "9xl" }} fontWeight="bold" lineHeight="1" letterSpacing="tighter">
                                {formattedMonthTotal}
                            </Text>
                        </Box>
                    </Flex>
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
                    </>
                )}
            </Stack>
        </Center>
    );
}