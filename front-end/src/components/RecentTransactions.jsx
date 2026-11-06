import { Box, HStack, Stack, Text } from "@chakra-ui/react";
import { transactionsLink } from "../lib/budget";
import { splitName } from "../lib/categoryName";
import { latestSpending } from "../lib/dashboard";
import { formatDate, useLocale } from "../lib/locale";
import { formatCents } from "../lib/money";
import DashboardCard from "./DashboardCard";
import PersonAvatar from "./PersonAvatar";

// The latest spending of the month (`transactions` is already that month's), with the emoji of its category.
export default function RecentTransactions({ transactions, categories, month, members = [] }) {
    useLocale(); // amounts and dates follow the family's currency and language
    const latest = latestSpending(transactions);

    return (
        <DashboardCard title="Últimas transações" to={transactionsLink(month, "debit")} linkText="Ver todas">
            {latest.length === 0 ? (
                <Text color="fg.muted">Nenhum gasto neste mês.</Text>
            ) : (
                <Stack as="ul" listStyleType="none" gap={3} aria-label="Últimas transações">
                    {latest.map((t) => {
                        const category = categories.find((c) => String(c.id) === String(t.category_id));
                        const { emoji } = splitName(category?.name);
                        return (
                            <HStack as="li" key={t.id} gap={3}>
                                <Box aria-hidden="true" w="9" h="9" flexShrink={0} display="grid" placeItems="center" borderRadius="full" bg="bg.muted">
                                    {emoji || "•"}
                                </Box>
                                <Stack gap={0} flex="1" minW={0}>
                                    <Text truncate>{t.label}</Text>
                                    <Text fontSize="xs" color="fg.muted">
                                        {formatDate(t.transactioned_at, { day: "numeric", month: "short" })}
                                    </Text>
                                </Stack>
                                <PersonAvatar person={members.find((member) => member.id === t.user_id)} />
                                <Text fontWeight="medium">{formatCents(t.value)}</Text>
                            </HStack>
                        );
                    })}
                </Stack>
            )}
        </DashboardCard>
    );
}
