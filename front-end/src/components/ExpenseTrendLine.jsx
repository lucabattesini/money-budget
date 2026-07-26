import { Box, Heading, Text, Center } from "@chakra-ui/react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { useMemo } from "react";

const MONTH_NAMES = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"];

export default function ExpenseTrendLine({ transactions }) {
    const data = useMemo(() => {
        if (!transactions) return [];

        // Group transactions by month/year
        const monthMap = {};

        transactions.forEach(t => {
            const tDate = new Date(t.date);
            const m = tDate.getMonth();
            const y = tDate.getFullYear();
            const key = `${y}-${String(m).padStart(2, '0')}`;
            
            if (!monthMap[key]) {
                monthMap[key] = {
                    month: m,
                    year: y,
                    label: `${MONTH_NAMES[m]} ${y}`,
                    total: 0
                };
            }
            monthMap[key].total += (t.value / 100);
        });

        // Convert to array and sort chronologically
        const sortedMonths = Object.keys(monthMap)
            .sort()
            .map(key => monthMap[key]);

        return sortedMonths;
    }, [transactions]);

    return (
        <Box w="full" h="300px" p={4} borderRadius="lg">
            <Heading size="md" mb={4} textAlign="center">Evolução dos Gastos</Heading>
            {data.length === 0 ? (
                <Center h="200px">
                    <Text color="gray.500">Nenhum gasto registrado.</Text>
                </Center>
            ) : (
                <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={data} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                        <CartesianGrid strokeDasharray="3 3" vertical={false} />
                        <XAxis dataKey="label" />
                        <YAxis tickFormatter={(value) => `R$ ${value}`} />
                        <Tooltip formatter={(value) => `R$ ${value.toFixed(2)}`} />
                        <Line type="monotone" dataKey="total" stroke="#00C49F" strokeWidth={3} dot={{ r: 5 }} activeDot={{ r: 8 }} />
                    </LineChart>
                </ResponsiveContainer>
            )}
        </Box>
    );
}
