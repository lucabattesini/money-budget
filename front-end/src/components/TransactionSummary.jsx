import { Flex, Box, Text } from "@chakra-ui/react";
import { familyNow, formatMoney, useLocale } from "../lib/locale";

export default function TransactionSummary({ transactions }) {
    useLocale(); // show amounts in the family's currency
    const now = familyNow();
    
    const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    
    const startOfWeek = new Date(startOfToday);
    startOfWeek.setDate(startOfWeek.getDate() - 7);

    const startOfMonth = new Date(now.getFullYear(), now.getMonth(), 1);

    let todaySum = 0;
    let weekSum = 0;
    let monthSum = 0;

    // Credits are money coming in; these totals are what was spent
    transactions.filter(transaction => transaction.type !== "credit").forEach(transaction => {
        const tDate = new Date(transaction.transactioned_at);
        const value = transaction.value / 100;

        if (tDate >= startOfToday) {
            todaySum += value;
        } 
        if (tDate >= startOfWeek) {
            weekSum += value;
        } 
        if (tDate >= startOfMonth) {
            monthSum += value;
        }
    });

    const formatCurrency = (val) => formatMoney(val);

    return (
        <Flex w="full" justify="space-between" mb={{ base: 4, md: 8 }} gap={{ base: 2, md: 4 }}>
            <Box flex="1" textAlign="center">
                <Text fontSize="xs" color="gray.400" textTransform="uppercase" fontWeight="bold" mb={1}>Hoje</Text>
                <Text fontSize={{ base: "md", md: "xl" }} color="white" fontWeight="bold">{formatCurrency(todaySum)}</Text>
            </Box>
            <Box flex="1" textAlign="center" borderLeft="1px solid" borderRight="1px solid" borderColor="gray.700">
                <Text fontSize="xs" color="gray.400" textTransform="uppercase" fontWeight="bold" mb={1}>Últimos 7 dias</Text>
                <Text fontSize={{ base: "md", md: "xl" }} color="white" fontWeight="bold">{formatCurrency(weekSum)}</Text>
            </Box>
            <Box flex="1" textAlign="center">
                <Text fontSize="xs" color="gray.400" textTransform="uppercase" fontWeight="bold" mb={1}>Este Mês</Text>
                <Text fontSize={{ base: "md", md: "xl" }} color="white" fontWeight="bold">{formatCurrency(monthSum)}</Text>
            </Box>
        </Flex>
    );
}
