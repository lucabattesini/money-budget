import { Box, Heading, Text, Center } from "@chakra-ui/react";
import { BarList, useChart } from "@chakra-ui/charts";
import { useMemo } from "react";

export default function TopCategoriesBarList({ transactions, categories }) {
    const data = useMemo(() => {
        if (!transactions || !categories) return [];

        // Sum by category for all-time
        const sums = {};
        transactions.forEach(t => {
            if (!sums[t.category]) sums[t.category] = 0;
            sums[t.category] += (t.value / 100);
        });

        // Map to chart data, sort and slice top 5
        const organized = Object.keys(sums).map((catId) => {
            const cat = categories.find(c => String(c.id) === String(catId));
            return {
                name: cat ? cat.name : "Desconhecido",
                value: sums[catId]
            };
        });

        organized.sort((a, b) => b.value - a.value);
        return organized.slice(0, 5);
    }, [transactions, categories]);

    const chart = useChart({
        sort: { by: "value", direction: "desc" },
        data: data,
        series: [{ name: "name", color: "blue.subtle" }],
    });

    return (
        <Box w="full" p={4} borderRadius="lg">
            <Heading size="md" mb={4} textAlign="center">Top 5 Categorias</Heading>
            {data.length === 0 ? (
                <Center h="100px">
                    <Text color="gray.500">Nenhum gasto registrado.</Text>
                </Center>
            ) : (
                <Box width="100%">
                    <BarList.Root chart={chart}>
                        <BarList.Content>
                            <BarList.Bar />
                            <BarList.Value />
                        </BarList.Content>
                    </BarList.Root>
                </Box>
            )}
        </Box>
    );
}
