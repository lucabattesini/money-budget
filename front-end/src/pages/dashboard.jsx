import { useState, useEffect, useMemo, useRef } from "react";
import { Box, Center, Grid, Heading, HStack, IconButton, Stack } from "@chakra-ui/react";
import { useSearchParams } from "react-router-dom";
import { LuChevronLeft, LuChevronRight } from "react-icons/lu";
import { getAllCategories, getTransactions, getMe, getBudgets, getFamily } from "../api/endpoints";
import { getToken } from "../lib/auth";
import { monthFromLink, monthKey, monthLabel, shiftMonth } from "../lib/budget";
import { countsAsIncoming, countsAsSpending, spendingOfMonth, sumCents, transactionsOfMonth } from "../lib/dashboard";
import { familyNow, useLocale } from "../lib/locale";
import customToaster from "../utils/customToaster";
import DashboardSkeleton from "../components/DashboardSkeleton";
import BudgetRing from "../components/BudgetRing";
import CashFlowCard from "../components/CashFlowCard";
import SpendingCard from "../components/SpendingCard";
import RecentTransactions from "../components/RecentTransactions";
import TopCategoriesBarList from "../components/TopCategoriesBarList";

export default function Dashboard() {
    const { timezone } = useLocale(); // amounts and the month name follow the family's currency and language; "today" its timezone
    const [categories, setCategories] = useState([]);
    const [categoriesLoaded, setCategoriesLoaded] = useState(false);
    // The transactions the cards are drawn from, with the month they were asked for: null until the first answer. When the
    // person changes month the cards stay (dimmed) on the month they show until the new answer arrives, instead of
    // blanking the page, and a month already seen is shown at once while it is asked for again quietly.
    const [loaded, setLoaded] = useState(null);
    const seen = useRef(new Map());
    const loading = !categoriesLoaded || loaded === null;
    const [user, setUser] = useState(null);
    const [members, setMembers] = useState([]); // the family, to show whose each transaction is
    // eslint-disable-next-line react-hooks/exhaustive-deps -- read again only when the family's timezone arrives or changes
    const now = useMemo(() => familyNow(), [timezone]);
    const thisMonth = monthKey(now);
    // Every card shows this month. It lives in the address (?month=2026-03), so reloading or sharing the page keeps it;
    // this month is the default and needs no parameter. A month that is missing, invalid or still to come is this month.
    const [params, setParams] = useSearchParams();
    const requested = monthFromLink(params.get("month"), thisMonth);
    const month = requested > thisMonth ? thisMonth : requested;
    const setMonth = (key) => setParams(key === thisMonth ? {} : { month: key }, { replace: true });
    const shownMonth = loaded?.month ?? month;
    const refreshing = !loading && loaded.month !== month;
    // After an expired login the token is gone and the user is on the login page: no message there
    // (One message, however many of the calls failed)
    const toldLoadFailed = useRef(false);
    const tellLoadFailed = () => {
        if (getToken() && !toldLoadFailed.current) {
            toldLoadFailed.current = true;
            customToaster("Error", "error", "Não foi possível carregar seus dados. Tente novamente mais tarde.");
        }
    };
    const [budget, setBudget] = useState(undefined); // the plan of the month: undefined while loading, null when it failed

    // What the page needs once: the categories, the person and the family. They are asked for together with the
    // transactions, and nothing waits for the person or the family (they only add the greeting and the names).
    useEffect(() => {
        const token = getToken();
        getAllCategories(token).then((data) => {
            if (data) setCategories(data.data);
            else tellLoadFailed();
            setCategoriesLoaded(true);
        });
        getMe(token).then((data) => {
            if (data?.data) setUser(data.data);
        });
        getFamily(token).then((result) => {
            if (result?.ok) setMembers(result.data.members ?? []);
        });
    }, []);

    // The transactions of the month on the page and of the month before it (the spending card compares the two): not the
    // whole history, which would grow with every month the family uses the app. Written as the family's wall-clock days,
    // like the transactions themselves. An answer for a month that is no longer on the page is ignored.
    useEffect(() => {
        let current = true;
        if (seen.current.has(month)) setLoaded({ month, transactions: seen.current.get(month) });
        const query = { start: `${shiftMonth(month, -1)}-01T00:00:00`, end: `${shiftMonth(month, 1)}-01T00:00:00` };
        getTransactions(query, getToken()).then((data) => {
            if (!current) return;
            if (data) {
                seen.current.set(month, data.data);
                setLoaded({ month, transactions: data.data });
            } else {
                setLoaded({ month, transactions: [] });
                tellLoadFailed();
            }
        });
        return () => {
            current = false;
        };
    }, [month]);

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
    const outgoing = useMemo(() => countsAsSpending(loaded?.transactions ?? [], categories), [loaded, categories]);
    const spending = useMemo(() => spendingOfMonth(outgoing, shownMonth), [outgoing, shownMonth]);
    // What came in: credits, but not the other side of a transfer between accounts
    const entered = useMemo(() => sumCents(transactionsOfMonth(countsAsIncoming(loaded?.transactions ?? [], categories), shownMonth)), [loaded, categories, shownMonth]);

    return (
        <Center>
            <Stack minHeight="100dvh" gap={6} w="full" py={{ base: 6, md: 10 }} px={{ base: 4, md: 8 }}>
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
                        <Heading size="md" minW={{ base: "8rem", md: "10rem" }} textAlign="center" textTransform="capitalize" aria-live="polite">
                            {monthLabel(month)}
                        </Heading>
                        <IconButton aria-label="Próximo mês" variant="outline" size="sm" disabled={month >= thisMonth} onClick={() => setMonth(shiftMonth(month, 1))}>
                            <LuChevronRight />
                        </IconButton>
                    </HStack>
                </HStack>

                {loading ? (
                    <DashboardSkeleton />
                ) : (
                    <Grid aria-busy={refreshing} opacity={refreshing ? 0.5 : 1} transition="opacity 0.15s" templateColumns={{ base: "minmax(0, 1fr)", lg: "3fr 2fr" }} gap={6} alignItems="start">
                        {/* On a phone the two columns become one list and the chart goes last (order); on a wide screen they are columns */}
                        <Stack gap={6} display={{ base: "contents", lg: "flex" }}>
                            <Box order={{ base: 1, lg: 0 }}><BudgetRing budget={budget} month={month} /></Box>
                            <Box order={{ base: 2, lg: 0 }}><CashFlowCard entered={entered} spent={sumCents(spending)} month={shownMonth} /></Box>
                            <Box order={{ base: 5, lg: 0 }}><SpendingCard transactions={outgoing} month={shownMonth} now={now} /></Box>
                        </Stack>
                        <Stack gap={6} display={{ base: "contents", lg: "flex" }}>
                            <Box order={{ base: 3, lg: 0 }}><RecentTransactions transactions={spending} categories={categories} month={shownMonth} members={members} /></Box>
                            {/* key: a new month starts with the list closed again */}
                            <Box order={{ base: 4, lg: 0 }}><TopCategoriesBarList key={shownMonth} transactions={spending} categories={categories} /></Box>
                        </Stack>
                    </Grid>
                )}
            </Stack>
        </Center>
    );
}
