import { Box, Heading, Text, Center, Stack, Flex } from "@chakra-ui/react";
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from "recharts";
import { useMemo } from "react";

const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042', '#8884d8', '#ff6f61', '#6b5b95'];

export default function CategoryPieChart({ transactions, categories }) {
    const data = useMemo(() => {
        if (!transactions || !categories) return [];

        // Sum by category for all-time
        const sums = {};
        transactions.forEach(t => {
            if (!sums[t.category]) sums[t.category] = 0;
            sums[t.category] += (t.value / 100);
        });

        // Map to chart data
        const mappedData = Object.keys(sums).map((catId) => {
            const cat = categories.find(c => String(c.id) === String(catId));
            return {
                name: cat ? cat.name : "Desconhecido",
                value: sums[catId]
            };
        }).filter(item => item.value > 0);

        // Sort descending so the legend can pick the top 5
        mappedData.sort((a, b) => b.value - a.value);

        // Assign colors after sorting so the biggest slices get distinct colors
        return mappedData.map((item, index) => ({ ...item, color: COLORS[index % COLORS.length] }));
    }, [transactions, categories]);

    // Recharts 3 ignores Legend's payload prop, so render the top 5 ourselves
    const renderLegend = () => (
        <Stack gap={1}>
            {data.slice(0, 5).map((item) => (
                <Flex key={item.name} align="center" gap={2}>
                    <Box w="10px" h="10px" bg={item.color} flexShrink={0} />
                    <Text fontSize="sm" color={item.color}>{item.name}</Text>
                </Flex>
            ))}
        </Stack>
    );

    return (
        <Box w="full" h="300px" p={4} borderRadius="lg">
            <Heading size="md" mb={4} textAlign="center">Gastos por Categoria</Heading>
            {data.length === 0 ? (
                <Center h="200px">
                    <Text color="gray.500">Nenhum gasto registrado.</Text>
                </Center>
            ) : (
                <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                        <Pie
                            data={data}
                            cx="50%"
                            cy="50%"
                            outerRadius={80}
                            dataKey="value"
                            stroke="none"
                        >
                            {data.map((entry, index) => (
                                <Cell key={`cell-${index}`} fill={entry.color} stroke="none" />
                            ))}
                        </Pie>
                        <Tooltip formatter={(value) => `R$ ${value.toFixed(2)}`} />
                        <Legend 
                            layout="vertical" 
                            verticalAlign="middle" 
                            align="left" 
                            content={renderLegend}
                        />
                    </PieChart>
                </ResponsiveContainer>
            )}
        </Box>
    );
}
