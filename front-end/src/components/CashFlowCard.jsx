import { Box, HStack, Separator, Stack, Text } from "@chakra-ui/react";
import { useLocale } from "../lib/locale";
import { formatCents } from "../lib/money";
import DashboardCard from "./DashboardCard";

// One line of the panel: a name, the amount and a bar as long as the amount is, compared with the larger of the two.
function Flow({ label, ariaLabel, cents, largest, color }) {
    return (
        <Stack gap={1}>
            <HStack justify="space-between">
                <Text fontSize="sm" color="fg.muted">{label}</Text>
                <Text fontSize="lg" fontWeight="bold" aria-label={ariaLabel}>{formatCents(cents)}</Text>
            </HStack>
            <Box h="2" borderRadius="full" bg="bg.muted" overflow="hidden" aria-hidden="true">
                <Box h="full" borderRadius="full" bg={color} w={largest > 0 ? `${(cents / largest) * 100}%` : "0%"} />
            </Box>
        </Stack>
    );
}

// What came in and what went out in the month, and what was left over. Both are in cents.
export default function CashFlowCard({ entered, spent }) {
    useLocale(); // amounts follow the family's currency
    const balance = entered - spent;
    const largest = Math.max(entered, spent);

    return (
        <DashboardCard title="Entradas e saídas">
            <Stack gap={4}>
                <Flow label="Entradas" ariaLabel="Entradas do mês" cents={entered} largest={largest} color="green.500" />
                <Flow label="Saídas" ariaLabel="Saídas do mês" cents={spent} largest={largest} color="red.500" />
                <Separator />
                <HStack justify="space-between" align="baseline">
                    <Stack gap={0}>
                        <Text fontSize="sm" color="fg.muted">Saldo do mês</Text>
                        {largest === 0 ? (
                            <Text fontSize="xs" color="fg.muted">Nenhuma entrada ou saída neste mês.</Text>
                        ) : (
                            <Text fontSize="xs" color="fg.muted">{balance >= 0 ? "sobrou" : "faltou"}</Text>
                        )}
                    </Stack>
                    <Text fontSize="xl" fontWeight="bold" color={balance < 0 ? "fg.error" : balance > 0 ? "green.600" : undefined} aria-label="Saldo do mês">
                        {balance < 0 ? "−" : ""}{formatCents(Math.abs(balance))}
                    </Text>
                </HStack>
            </Stack>
        </DashboardCard>
    );
}
