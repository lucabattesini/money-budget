import { Box, Flex, HStack, SimpleGrid, Stack, Text } from "@chakra-ui/react";
import { transactionsLink } from "../lib/budget";
import { useLocale } from "../lib/locale";
import { formatCents } from "../lib/money";
import DashboardCard from "./DashboardCard";

// One of the two figures under the bar: a coloured dot, the name and the amount.
function Figure({ label, ariaLabel, cents, color }) {
    return (
        <Stack gap={0}>
            <HStack gap={1.5}>
                <Box boxSize="2" borderRadius="full" bg={color} aria-hidden="true" />
                <Text fontSize="xs" color="fg.muted">{label}</Text>
            </HStack>
            <Text fontSize="md" fontWeight="semibold" aria-label={ariaLabel}>{formatCents(cents)}</Text>
        </Stack>
    );
}

// What came in and what went out in the month, and what was left over. Both are in cents.
// One bar as long as what came in: the red part went out, the green part is what is left (all red when more went out
// than came in).
export default function CashFlowCard({ entered, spent, month }) {
    useLocale(); // amounts follow the family's currency
    const balance = entered - spent;
    const nothing = entered === 0 && spent === 0;
    const spentShare = nothing ? 0 : entered <= 0 ? 100 : Math.min(100, (spent / entered) * 100);

    return (
        <DashboardCard title="Entradas e saídas" to={transactionsLink(month)} linkText="Ver transações">
            <Stack gap={3}>
                <Flex justify="space-between" align="baseline" gap={3}>
                    <Stack gap={0}>
                        <Text fontSize="sm" color="fg.muted">Saldo do mês</Text>
                        <Text fontSize="xs" color="fg.muted">
                            {nothing ? "Nenhuma entrada ou saída neste mês." : balance >= 0 ? "sobrou" : "faltou"}
                        </Text>
                    </Stack>
                    <Text fontSize="2xl" fontWeight="bold" color={balance < 0 ? "fg.error" : balance > 0 ? "green.600" : undefined} aria-label="Saldo do mês">
                        {balance < 0 ? "−" : ""}{formatCents(Math.abs(balance))}
                    </Text>
                </Flex>

                <Flex h="2.5" borderRadius="full" bg="bg.muted" overflow="hidden" aria-hidden="true">
                    <Box h="full" bg="red.500" data-part="spent" style={{ width: `${spentShare}%` }} />
                    {!nothing && balance > 0 && <Box h="full" bg="green.500" flex="1" data-part="left" />}
                </Flex>

                <SimpleGrid columns={2} gap={3}>
                    <Figure label="Entradas" ariaLabel="Entradas do mês" cents={entered} color="green.500" />
                    <Figure label="Saídas" ariaLabel="Saídas do mês" cents={spent} color="red.500" />
                </SimpleGrid>
            </Stack>
        </DashboardCard>
    );
}
