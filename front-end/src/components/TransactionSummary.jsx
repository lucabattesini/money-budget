import { Flex, Box, Text } from "@chakra-ui/react";

export default function TransactionSummary({ transactions }) {
    const now = new Date();
    
    const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    
    const startOfWeek = new Date(startOfToday);
    startOfWeek.setDate(startOfWeek.getDate() - 7);

    const startOfMonth = new Date(now.getFullYear(), now.getMonth(), 1);

    let todaySum = 0;
    let weekSum = 0;
    let monthSum = 0;

    transactions.forEach(transaction => {
        const tDate = new Date(transaction.date);
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

    const formatCurrency = (val) => {
        return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(val);
    };

    return (
        <Flex w="full" justify="space-between" mb={8} gap={4}>
            <Box flex="1" textAlign="center">
                <Text fontSize="xs" color="gray.400" textTransform="uppercase" fontWeight="bold" mb={1}>Hoje</Text>
                <Text fontSize="xl" color="white" fontWeight="bold">{formatCurrency(todaySum)}</Text>
            </Box>
            <Box flex="1" textAlign="center" borderLeft="1px solid" borderRight="1px solid" borderColor="gray.700">
                <Text fontSize="xs" color="gray.400" textTransform="uppercase" fontWeight="bold" mb={1}>Últimos 7 dias</Text>
                <Text fontSize="xl" color="white" fontWeight="bold">{formatCurrency(weekSum)}</Text>
            </Box>
            <Box flex="1" textAlign="center">
                <Text fontSize="xs" color="gray.400" textTransform="uppercase" fontWeight="bold" mb={1}>Este Mês</Text>
                <Text fontSize="xl" color="white" fontWeight="bold">{formatCurrency(monthSum)}</Text>
            </Box>
        </Flex>
    );
}
