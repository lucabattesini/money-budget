import { useEffect, useRef, useState } from "react";
import { Link as RouterLink } from "react-router-dom";
import { Box, Button, CloseButton, Drawer, Flex, HStack, Link, Portal, SimpleGrid, Spinner, Stack, Text, Wrap } from "@chakra-ui/react";
import { getCategoryHistory } from "../api/endpoints";
import { getToken } from "../lib/auth";
import { budgetStatus, monthDays, monthLabel } from "../lib/budget";
import { plainName } from "../lib/categoryName";
import { formatDate } from "../lib/locale";
import { formatBudgetCents, formatCents } from "../lib/money";
import useBackClosesOverlay from "../lib/useBackClosesOverlay";

const COLORS = { ok: "green.solid", warn: "orange.solid", limit: "blue.solid", over: "red.solid", none: "gray.solid" };
const BAR_AREA = 120; // px: the height of the tallest bar

const shortMonth = (key) => {
    const [year, month] = key.split("-").map(Number);
    return formatDate(new Date(year, month - 1, 1), { month: "short" });
};

// One category over time, to plan with: what was spent in each of the last months against what was planned (tap a
// month to see its transactions), the average, and the transactions of the chosen month.
export default function CategoryHistoryDrawer({ category, month, open, onClose, onUseBudget, reloadKey = 0 }) {
    useBackClosesOverlay(open, onClose);
    const [months, setMonths] = useState(6);
    const [shown, setShown] = useState(month); // the month whose transactions are listed
    const [data, setData] = useState(null);
    const [failed, setFailed] = useState(false);
    const lastCategory = useRef(category); // the title stays while the panel slides away
    if (category) lastCategory.current = category;
    const [using, setUsing] = useState(null); // the suggestion being saved
    const [reloaded, setReloaded] = useState(0); // asked again after a budget was set here

    useEffect(() => {
        if (open) setShown(month); // every opening starts on the month of the page
    }, [open, month]);

    useEffect(() => {
        if (!open || !category) return undefined;
        let current = true;
        (async () => {
            const result = await getCategoryHistory(category.id, month, months, shown, getToken());
            if (!current) return;
            setFailed(!result.ok);
            setData(result.ok ? result.data : null); // an error is not shown next to the figures of the last answer
        })();
        return () => {
            current = false;
        };
    }, [open, category, month, months, shown, reloadKey, reloaded]);

    useEffect(() => {
        if (!open) {
            setData(null);
            setFailed(false);
            setMonths(6);
        }
    }, [open]);

    const history = data?.history ?? [];
    const tallest = Math.max(1, ...history.map((entry) => Math.max(entry.spent, entry.budgeted ?? 0)));
    // Suggestions come from the months that are over (the month of the page may be half spent), starting at the first
    // month with any spending or plan (the empty months before it would only pull the average and the minimum down)
    const past = history.filter((entry) => entry.month < month);
    const firstUsed = past.findIndex((entry) => entry.spent > 0 || entry.budgeted != null);
    const lived = firstUsed === -1 ? [] : past.slice(firstUsed);
    const spentBefore = lived.map((entry) => entry.spent);
    const whole = (cents) => Math.round(cents / 100) * 100; // budgets are meant to be round
    const average = spentBefore.length ? Math.round(spentBefore.reduce((sum, value) => sum + value, 0) / spentBefore.length) : 0;
    const suggestions = lived.length
        ? [
              { id: "average", label: "Média", cents: whole(average) },
              { id: "max", label: "Máximo", cents: whole(Math.max(...spentBefore)) },
              { id: "min", label: "Mínimo", cents: whole(Math.min(...spentBefore)) },
              { id: "last", label: "Mês passado", cents: whole(past[past.length - 1].spent) },
          ].filter((suggestion) => suggestion.cents > 0) // a chip of R$ 0 would plan "spend nothing": not a suggestion
        : [];
    const applySuggestion = async (suggestion) => {
        setUsing(suggestion.id);
        const saved = await onUseBudget(suggestion.cents);
        setUsing(null);
        if (saved) setReloaded((count) => count + 1);
    };
    const current = history.find((entry) => entry.month === shown);
    const name = category ? plainName(category.name) : "";

    return (
        <Drawer.Root open={open} onOpenChange={(e) => !e.open && onClose()} placement="end" size={{ base: "full", md: "md" }}>
            <Portal>
                <Drawer.Backdrop />
                <Drawer.Positioner>
                    <Drawer.Content>
                        <Drawer.Header>
                            <Drawer.Title>{(category ?? lastCategory.current)?.name}</Drawer.Title>
                        </Drawer.Header>
                        <Drawer.Body>
                            {failed && <Text color="fg.error">Não foi possível carregar o histórico. Tente novamente mais tarde.</Text>}
                            {!failed && !data && <Spinner size="lg" />}
                            {data && (
                                <Stack gap={8}>
                                    <Stack gap={2}>
                                        <HStack justify="space-between">
                                            <Text fontWeight="semibold">Últimos {history.length} meses</Text>
                                            <Button size="xs" variant="ghost" onClick={() => {
                                                    setMonths(months === 6 ? 12 : 6);
                                                    setShown(month); // the tapped month may not be in the other window
                                                }}>
                                                {months === 6 ? "Ver 12 meses" : "Ver 6 meses"}
                                            </Button>
                                        </HStack>
                                        <Flex gap={1} align="end" role="group" aria-label={`Gasto de ${name} por mês`}>
                                            {history.map((entry) => {
                                                const { state } = budgetStatus(entry.spent, entry.budgeted);
                                                const selected = entry.month === shown;
                                                return (
                                                    <Button
                                                        key={entry.month}
                                                        variant="plain"
                                                        flex="1"
                                                        minW={0}
                                                        h="auto"
                                                        px={0}
                                                        py={1}
                                                        flexDirection="column"
                                                        gap={1}
                                                        aria-pressed={selected}
                                                        aria-label={`${monthLabel(entry.month)}: gasto ${formatBudgetCents(entry.spent)}${entry.budgeted != null ? ` de ${formatBudgetCents(entry.budgeted)}` : ""}`}
                                                        onClick={() => setShown(entry.month)}
                                                        bg={selected ? "bg.muted" : undefined}
                                                    >
                                                        <Box position="relative" w="full" h={`${BAR_AREA}px`} display="flex" alignItems="end" justifyContent="center">
                                                            <Box
                                                                w="60%"
                                                                borderTopRadius="sm"
                                                                bg={COLORS[state]}
                                                                style={{ height: `${Math.max(entry.spent > 0 ? 2 : 0, Math.round((entry.spent / tallest) * BAR_AREA))}px` }}
                                                            />
                                                            {entry.budgeted != null && (
                                                                <Box
                                                                    position="absolute"
                                                                    left="10%"
                                                                    right="10%"
                                                                    borderTopWidth="2px"
                                                                    borderStyle="dashed"
                                                                    borderColor="fg"
                                                                    style={{ bottom: `${Math.round((entry.budgeted / tallest) * BAR_AREA)}px` }}
                                                                    aria-hidden="true"
                                                                />
                                                            )}
                                                        </Box>
                                                        <Text fontSize="xs" color={selected ? "fg" : "fg.muted"} fontWeight={selected ? "semibold" : "normal"} textTransform="capitalize">
                                                            {shortMonth(entry.month)}
                                                        </Text>
                                                    </Button>
                                                );
                                            })}
                                        </Flex>
                                        <Text fontSize="xs" color="fg.muted">A linha tracejada é o orçamento do mês. Toque em um mês para ver as transações.</Text>
                                    </Stack>

                                    <SimpleGrid columns={3} gap={2}>
                                        <Stack gap={0}>
                                            <Text fontSize="xs" color="fg.muted">Média por mês</Text>
                                            <Text fontWeight="bold">{formatBudgetCents(average)}</Text>
                                        </Stack>
                                        <Stack gap={0}>
                                            <Text fontSize="xs" color="fg.muted">Orçado</Text>
                                            <Text fontWeight="bold">{current?.budgeted != null ? formatBudgetCents(current.budgeted) : "—"}</Text>
                                        </Stack>
                                        <Stack gap={0}>
                                            <Text fontSize="xs" color="fg.muted">Gasto</Text>
                                            <Text fontWeight="bold">{formatBudgetCents(current?.spent ?? 0)}</Text>
                                        </Stack>
                                    </SimpleGrid>

                                    {suggestions.length > 0 && onUseBudget && (
                                        <Stack gap={1.5} role="group" aria-label="Sugestões de orçamento">
                                            <Text fontSize="sm" color="fg.muted">Usar como orçamento de {monthLabel(month)}:</Text>
                                            <Wrap gap={2}>
                                                {suggestions.map((suggestion) => (
                                                    <Button
                                                        key={suggestion.id}
                                                        size="xs"
                                                        variant="outline"
                                                        rounded="full"
                                                        minH={{ base: "36px", md: "auto" }}
                                                        loading={using === suggestion.id}
                                                        disabled={using !== null}
                                                        aria-label={`${suggestion.label}: usar ${formatBudgetCents(suggestion.cents)} como orçamento`}
                                                        onClick={() => applySuggestion(suggestion)}
                                                    >
                                                        <Text as="span" color="fg.muted">{suggestion.label}</Text>
                                                        <Text as="span" fontWeight="bold">{formatBudgetCents(suggestion.cents)}</Text>
                                                    </Button>
                                                ))}
                                            </Wrap>
                                        </Stack>
                                    )}

                                    <Stack gap={2}>
                                        <HStack justify="space-between" align="baseline">
                                            <Text fontWeight="semibold" textTransform="capitalize">{monthLabel(data.transactions_month)}</Text>
                                            <Link asChild fontSize="sm" variant="underline">
                                                <RouterLink to={`/transactions?category=${data.category.id}&from=${monthDays(data.transactions_month).from}&to=${monthDays(data.transactions_month).to}&type=debit`}>
                                                    Ver na lista de transações
                                                </RouterLink>
                                            </Link>
                                        </HStack>
                                        {data.transactions.length === 0 ? (
                                            <Text color="fg.muted" fontSize="sm">Nenhum gasto nesta categoria neste mês.</Text>
                                        ) : (
                                            <Stack as="ul" listStyleType="none" gap={0} aria-label={`Transações de ${name}`}>
                                                {data.transactions.map((transaction) => (
                                                    <HStack as="li" key={transaction.id} justify="space-between" gap={3} py={2} borderTopWidth="1px" opacity={transaction.excluded ? 0.6 : 1}>
                                                        <Stack gap={0} minW={0}>
                                                            <Text wordBreak="break-word">{transaction.label}</Text>
                                                            <Text fontSize="xs" color="fg.muted">
                                                                {formatDate(transaction.transactioned_at)}
                                                                {transaction.user_name ? ` · ${transaction.user_name.split(" ")[0]}` : ""}
                                                                {transaction.excluded && " · fora dos totais"}
                                                            </Text>
                                                        </Stack>
                                                        <Text whiteSpace="nowrap" fontWeight="medium">{formatCents(transaction.value)}</Text>
                                                    </HStack>
                                                ))}
                                            </Stack>
                                        )}
                                    </Stack>
                                </Stack>
                            )}
                        </Drawer.Body>
                        <Drawer.CloseTrigger asChild>
                            <CloseButton size="sm" />
                        </Drawer.CloseTrigger>
                    </Drawer.Content>
                </Drawer.Positioner>
            </Portal>
        </Drawer.Root>
    );
}
