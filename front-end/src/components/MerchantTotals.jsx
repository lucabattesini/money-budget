import { Box, HStack, Stack, Text } from "@chakra-ui/react";
import { formatCents } from "../lib/money";
import { useLocale } from "../lib/locale";

const SHOWN = 5;

// How much went to each merchant, in the transactions on screen (the filters apply). Only what was spent counts:
// credits are money coming in. Transactions without a merchant are not in the list.
export default function MerchantTotals({ transactions, merchants }) {
    useLocale(); // amounts follow the family's currency and language
    const totals = new Map();
    transactions
        .filter((transaction) => !transaction.excluded && transaction.type !== "credit" && transaction.merchant_id != null)
        .forEach((transaction) => {
            totals.set(transaction.merchant_id, (totals.get(transaction.merchant_id) ?? 0) + transaction.value);
        });
    const rows = [...totals]
        .map(([id, cents]) => ({ id, cents, name: merchants.find((merchant) => merchant.id === id)?.name }))
        .filter((row) => row.name)
        .sort((a, b) => b.cents - a.cents)
        .slice(0, SHOWN);
    if (rows.length === 0) return null;

    return (
        <Box as="section" aria-label="Por estabelecimento" w="full" borderWidth="1px" borderRadius="lg" px={4} py={3}>
            <Text fontSize="xs" color="gray.400" textTransform="uppercase" fontWeight="bold" mb={2}>Por estabelecimento</Text>
            <Stack as="ul" listStyleType="none" gap={1} m={0} p={0}>
                {rows.map((row) => (
                    <HStack as="li" key={row.id} justify="space-between">
                        <Text truncate>{row.name}</Text>
                        <Text fontWeight="medium">{formatCents(row.cents)}</Text>
                    </HStack>
                ))}
            </Stack>
        </Box>
    );
}
