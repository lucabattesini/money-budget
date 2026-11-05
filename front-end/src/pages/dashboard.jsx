import { useState, useEffect, useMemo } from "react";
import { Box, Center, Grid, Heading, HStack, IconButton, Stack } from "@chakra-ui/react";
import { useSearchParams } from "react-router-dom";
import { LuChevronLeft, LuChevronRight } from "react-icons/lu";
import { getAllCategories, getTransactions, getMe, getBudgets } from "../api/endpoints";
import { getToken } from "../lib/auth";
import { monthFromLink, monthKey, monthLabel, shiftMonth } from "../lib/budget";
import { countsAsIncoming, countsAsSpending, spendingOfMonth, sumCents, transactionsOfMonth } from "../lib/dashboard";
import { familyNow, useLocale } from "../lib/locale";
import customToaster from "../utils/customToaster";
import { SpinnerLoading } from "../components/spinnerLoading";
import BudgetRing from "../components/BudgetRing";
import CashFlowCard from "../components/CashFlowCard";
import SpendingCard from "../components/SpendingCard";
import RecentTransactions from "../components/RecentTransactions";
import TopCategoriesBarList from "../components/TopCategoriesBarList";

export default function Dashboard() {
    const { timezone } = useLocale(); // amounts and the month name follow the family's currency and language; "today" its timezone
    const [loading, setLoading] = useState(true);
    const [categories, setCategories] = useState([]);
    const [transactions, setTransactions] = useState([]);
    const [user, setUser] = useState(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- read again only when the family's timezone arrives or changes
    const now = useMemo(() => familyNow(), [timezone]);
    const thisMonth = monthKey(now);
    // Every card shows this month. It lives in the address (?month=2026-03), so reloading or sharing the page keeps it;
    // this month is the default and needs no parameter. A month that is missing, invalid or still to come is this month.
    const [params, setParams] = useSearchParams();
    const requested = monthFromLink(params.get("month"), thisMonth);
    const month = requested > thisMonth ? thisMonth : requested;
    const setMonth = (key) => setParams(key === thisMonth ? {} : { month: key }, { replace: true });
    const [budget, setBudget] = useState(undefined); // the plan of the month: undefined while loading, null when it failed

    useEffect(() => {
        const token = getToken();
        // Request all transactions by passing null date filters
        const allTransactionsQuery = { organized_by: null, date: null };

        Promise.all([
            getAllCategories(token),
            getTransactions(allTransactionsQuery, token),
            getMe(token)
        ]).then(([categoriesData, transactionsData, userData]) => {
            // After an expired login the token is gone and the user is on the login page: no message there
            if ((!categoriesData || !transactionsData) && getToken()) {
                customToaster("Error", "error", "Não foi possível carregar seus dados. Tente novamente mais tarde.");
            }
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

    // The plan of the chosen month. An answer for a month that is no longer on the page is ignored.
    useEffect(() => {
        const token = getToken();
        if (!token) {
            setBudget(null); // no login (the user is being sent to the login page): nothing to wait for
            return;
        }
        let current = true;
        setBudget(undefined);
        getBudgets(month, token).then((result) => {
            if (current) setBudget(result.ok ? result.data : null);
        });
        return () => {
            current = false;
        };
    }, [month]);

    // Only money that was really spent: no credits, no transfers between accounts, like the budget
    const outgoing = useMemo(() => countsAsSpending(transactions, categories), [transactions, categories]);
    const spending = useMemo(() => spendingOfMonth(outgoing, month), [outgoing, month]);
    // What came in: credits, but not the other side of a transfer between accounts
    const entered = useMemo(() => sumCents(transactionsOfMonth(countsAsIncoming(transactions, categories), month)), [transactions, categories, month]);

    return (
        <Center>
            <Stack minHeight="100vh" gap={6} w="full" py={10} px={8}>
                <HStack justify="space-between" wrap="wrap" gap={4}>
                    {user ? (
                        <Heading size="xl">Olá, {user.name.split(' ')[0]} 👋</Heading>
                    ) : (
                        <Box />
                    )}
                    <HStack gap={2}>
                        <IconButton aria-label="Mês anterior" variant="outline" size="sm" onClick={() => setMonth(shiftMonth(month, -1))}>
                            <LuChevronLeft />
                        </IconButton>
                        <Heading size="md" minW="10rem" textAlign="center" textTransform="capitalize" aria-live="polite">
                            {monthLabel(month)}
                        </Heading>
                        <IconButton aria-label="Próximo mês" variant="outline" size="sm" disabled={month >= thisMonth} onClick={() => setMonth(shiftMonth(month, 1))}>
                            <LuChevronRight />
                        </IconButton>
                    </HStack>
                </HStack>

                {loading ? (
                    <SpinnerLoading />
                ) : (
                    <Grid templateColumns={{ base: "1fr", lg: "3fr 2fr" }} gap={6} alignItems="start">
                        {/* On a phone the two columns become one list and the chart goes last (order); on a wide screen they are columns */}
                        <Stack gap={6} display={{ base: "contents", lg: "flex" }}>
                            <Box order={{ base: 1, lg: 0 }}><BudgetRing budget={budget} month={month} /></Box>
                            <Box order={{ base: 2, lg: 0 }}><CashFlowCard entered={entered} spent={sumCents(spending)} month={month} /></Box>
                            <Box order={{ base: 5, lg: 0 }}><SpendingCard transactions={outgoing} month={month} now={now} /></Box>
                        </Stack>
                        <Stack gap={6} display={{ base: "contents", lg: "flex" }}>
                            <Box order={{ base: 3, lg: 0 }}><RecentTransactions transactions={spending} categories={categories} month={month} /></Box>
                            <Box order={{ base: 4, lg: 0 }}><TopCategoriesBarList transactions={spending} categories={categories} /></Box>
                        </Stack>
                    </Grid>
                )}
            </Stack>
        </Center>
    );
}
