import { useMemo } from "react";
import { Box, HStack, Stack, Text } from "@chakra-ui/react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { shiftMonth, transactionsLink } from "../lib/budget";
import { spendingByDay } from "../lib/dashboard";
import { formatDate, formatMoney, useLocale } from "../lib/locale";
import { formatCents } from "../lib/money";
import DashboardCard from "./DashboardCard";

const formatAxisValue = (value) => formatMoney(value, { notation: "compact", maximumFractionDigits: 1 });
const monthName = (key) => formatDate(new Date(Number(key.slice(0, 4)), Number(key.slice(5)) - 1, 1), { month: "long" });

// What was spent in the month, day by day, with the month before behind it to see if the pace is the same.
export default function SpendingCard({ transactions, month, now }) {
    useLocale(); // amounts and month names follow the family's currency and language
    const series = useMemo(() => spendingByDay(transactions, month, now), [transactions, month, now]);
    const data = series.days.map((d) => ({
        day: d.day,
        current: d.current === null ? null : d.current / 100,
        previous: d.previous === null ? null : d.previous / 100,
    }));
    const thisName = monthName(month);
    const previousName = monthName(shiftMonth(month, -1));
    const percent = series.change === null ? null : Math.round(Math.abs(series.change) * 100);

    return (
        <DashboardCard title="Gastos" to={transactionsLink(month, "debit")} linkText="Ver transações">
            <Stack gap={1} mb={4}>
                <Text fontSize="2xl" fontWeight="bold" lineHeight="1.1" aria-label="Total gasto no mês">
                    {formatCents(series.spent)}
                </Text>
                {percent !== null && (
                    <Text fontSize="sm" color={series.change > 0 ? "fg.error" : "fg.muted"}>
                        {percent === 0
                            ? `Igual a ${previousName} até o dia ${series.upToDay}`
                            : `${series.change > 0 ? "▲" : "▼"} ${percent}% ${series.change > 0 ? "a mais" : "a menos"} que ${previousName} até o dia ${series.upToDay}`}
                    </Text>
                )}
            </Stack>
            <Box h="240px" aria-label={`Gastos acumulados de ${thisName}, comparados com ${previousName}`}>
                <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={data} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                        <CartesianGrid strokeDasharray="3 3" vertical={false} />
                        <XAxis dataKey="day" />
                        <YAxis width={70} tickFormatter={formatAxisValue} />
                        <Tooltip
                            labelFormatter={(day) => `Dia ${day}`}
                            formatter={(value, name) => [formatMoney(value), name === "current" ? thisName : previousName]}
                        />
                        <Line type="monotone" dataKey="previous" stroke="#A0AEC0" strokeDasharray="5 5" strokeWidth={2} dot={false} connectNulls={false} />
                        <Line type="monotone" dataKey="current" stroke="#00C49F" strokeWidth={3} dot={false} connectNulls={false} />
                    </LineChart>
                </ResponsiveContainer>
            </Box>
            <HStack gap={4} mt={3} fontSize="xs" color="fg.muted">
                <HStack gap={1}><Box w="14px" h="3px" bg="#00C49F" /><Text>{thisName}</Text></HStack>
                <HStack gap={1}><Box w="14px" h="0" borderTopWidth="2px" borderStyle="dashed" borderColor="#A0AEC0" /><Text>{previousName}</Text></HStack>
            </HStack>
        </DashboardCard>
    );
}
