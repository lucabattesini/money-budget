import { Box, Button, Text, Center } from "@chakra-ui/react";
import DashboardCard from "./DashboardCard";
import { BarList, useChart } from "@chakra-ui/charts";
import { useMemo, useState } from "react";
import { LuChevronDown, LuChevronUp } from "react-icons/lu";
import { formatMoney, useLocale } from "../lib/locale";

const TOP = 5; // how many categories the panel shows until it is expanded

export default function TopCategoriesBarList({ transactions, categories }) {
    useLocale(); // the amounts follow the family's currency and language
    const [expanded, setExpanded] = useState(false);
    const all = useMemo(() => {
        if (!transactions || !categories) return [];

        // Sum by category (the page passes the spending of one month)
        const sums = {};
        transactions.forEach(t => {
            if (!sums[t.category_id]) sums[t.category_id] = 0;
            sums[t.category_id] += (t.value / 100);
        });

        // Map to chart data and sort, biggest first
        const organized = Object.keys(sums).map((catId) => {
            const cat = categories.find(c => String(c.id) === String(catId));
            return {
                name: cat ? cat.name : "Desconhecido",
                value: sums[catId]
            };
        });

        organized.sort((a, b) => b.value - a.value);
        return organized;
    }, [transactions, categories]);
    const canExpand = all.length > TOP;
    const data = expanded ? all : all.slice(0, TOP);

    const chart = useChart({
        sort: { by: "value", direction: "desc" },
        data: data,
        series: [{ name: "name", color: "blue.subtle" }],
    });

    return (
        <DashboardCard title="Principais categorias">
            {data.length === 0 ? (
                <Center h="100px">
                    <Text color="gray.500">Nenhum gasto registrado.</Text>
                </Center>
            ) : (
                <Box width="100%">
                    <BarList.Root chart={chart}>
                        <BarList.Content>
                            <BarList.Bar />
                            <BarList.Value valueFormatter={(value) => formatMoney(value)} />
                        </BarList.Content>
                    </BarList.Root>
                    {canExpand && (
                        <Button
                            variant="ghost"
                            size="sm"
                            mt={2}
                            minH={{ base: "44px", md: "auto" }}
                            aria-expanded={expanded}
                            onClick={() => setExpanded(!expanded)}
                        >
                            {expanded ? <LuChevronUp /> : <LuChevronDown />}
                            {expanded ? "Mostrar menos" : `Ver todas (${all.length})`}
                        </Button>
                    )}
                </Box>
            )}
        </DashboardCard>
    );
}
