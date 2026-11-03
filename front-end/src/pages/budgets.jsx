import { useCallback, useEffect, useRef, useState } from "react";
import { Badge, Box, Button, Heading, HStack, IconButton, Input, Progress, SimpleGrid, Spinner, Stack, Text } from "@chakra-ui/react";
import { LuChevronDown, LuChevronLeft, LuChevronRight, LuChevronUp, LuCopy } from "react-icons/lu";
import { copyBudgets, getBudgets, setBudget } from "../api/endpoints";
import { getToken } from "../lib/auth";
import { budgetStatus, monthKey, monthLabel, shiftMonth } from "../lib/budget";
import { plainName } from "../lib/categoryName";
import { useLocale } from "../lib/locale";
import { digitsToCents, formatCents, maskAmount } from "../lib/money";
import customToaster from "../utils/customToaster";

const BAR_COLORS = { ok: "green", warn: "orange", over: "red", none: "gray" };

const asText = (cents) => (cents ? maskAmount(String(cents)) : "");

// A thin bar showing how much of the plan is spent
function SpentBar({ spent, budgeted, label }) {
    const { state, percent } = budgetStatus(spent, budgeted);
    if (state === "none") return null;
    return (
        <Progress.Root value={percent} max={100} size="sm" colorPalette={BAR_COLORS[state]} aria-label={label} data-state-name={state}>
            <Progress.Track>
                <Progress.Range />
            </Progress.Track>
        </Progress.Root>
    );
}

function Stat({ label, value, color }) {
    return (
        <Stack gap={0}>
            <Text fontSize="sm" color="fg.muted">{label}</Text>
            <Text fontSize="2xl" fontWeight="bold" color={color}>{value}</Text>
        </Stack>
    );
}

// What is left of a plan, or how much it was exceeded by
function leftText(spent, budgeted) {
    if (!budgeted) return "";
    const left = budgeted - spent;
    return left >= 0 ? `Restam ${formatCents(left)}` : `Estourou ${formatCents(-left)}`;
}

// One month of the family's plan: what is planned for each spending category, what was spent and what is left.
export default function Budgets() {
    useLocale(); // amounts and the month name follow the family's currency and language
    const [month, setMonth] = useState(() => monthKey(new Date()));
    const [data, setData] = useState(null);
    const [failed, setFailed] = useState(false);
    const [drafts, setDrafts] = useState({}); // what is being typed, by category id, until it is saved
    const [opened, setOpened] = useState({}); // groups the person opened or closed by hand, by group id
    const [copying, setCopying] = useState(false);
    const shown = useRef(month); // an answer for a month that is no longer on the page must be ignored
    shown.current = month;

    const load = useCallback(async (key) => {
        const token = getToken();
        if (!token) return;
        const result = await getBudgets(key, token);
        if (shown.current !== key) return;
        if (!result.ok) {
            setFailed(true);
            return;
        }
        setFailed(false);
        setData(result.data);
    }, []);

    useEffect(() => {
        setData(null);
        setDrafts({});
        load(month);
    }, [month, load]);

    const clearDraft = (id) =>
        setDrafts((current) => {
            const next = { ...current };
            delete next[id];
            return next;
        });

    const save = async (category) => {
        const typed = drafts[category.id];
        if (typed === undefined) return;
        const cents = digitsToCents(typed);
        const forMonth = month;
        if (cents === (category.budgeted ?? 0)) {
            clearDraft(category.id);
            return;
        }
        const result = await setBudget(category.id, forMonth, cents, getToken());
        if (!result.ok) {
            customToaster("Erro", "error", result.detail || "Não foi possível salvar o orçamento. Tente novamente.");
            clearDraft(category.id); // back to what is saved
            return;
        }
        if (shown.current !== forMonth) return;
        setData(result.data);
        clearDraft(category.id);
    };

    const copyFromPreviousMonth = async () => {
        setCopying(true);
        const result = await copyBudgets(shiftMonth(month, -1), month, getToken());
        setCopying(false);
        if (!result.ok) {
            customToaster("Erro", "error", result.detail || "Não foi possível copiar. Tente novamente.");
            return;
        }
        const { copied, ...view } = result.data;
        if (shown.current === view.month) {
            setData(view);
            setDrafts({});
        }
        if (copied === 0) customToaster("Nada para copiar", "info", "O mês anterior não tem orçamentos que este mês ainda não tenha.");
        else customToaster("Pronto", "success", copied === 1 ? "1 orçamento copiado." : `${copied} orçamentos copiados.`);
    };

    const isOpen = (group) => opened[group.id] ?? (group.budgeted > 0 || group.categories.some((c) => c.spent > 0));

    return (
        <Stack gap={6} maxW="5xl" mx="auto" px={6} pt={10} pb={12}>
            <Stack gap={1}>
                <Heading size="2xl">Orçamentos</Heading>
                <Text color="fg.muted">
                    Planeje quanto gastar em cada categoria a cada mês e acompanhe o que já foi gasto. Só entram as saídas de dinheiro.
                </Text>
            </Stack>

            <HStack justify="space-between" wrap="wrap" gap={3}>
                <HStack gap={2}>
                    <IconButton aria-label="Mês anterior" variant="outline" size="sm" onClick={() => setMonth(shiftMonth(month, -1))}>
                        <LuChevronLeft />
                    </IconButton>
                    <Heading size="lg" minW="11rem" textAlign="center" textTransform="capitalize" aria-live="polite">
                        {monthLabel(month)}
                    </Heading>
                    <IconButton aria-label="Próximo mês" variant="outline" size="sm" onClick={() => setMonth(shiftMonth(month, 1))}>
                        <LuChevronRight />
                    </IconButton>
                </HStack>
                <Button variant="outline" size="sm" onClick={copyFromPreviousMonth} loading={copying} disabled={!data}>
                    <LuCopy /> Copiar do mês anterior
                </Button>
            </HStack>

            {failed && <Text color="fg.error">Não foi possível carregar o orçamento. Tente novamente mais tarde.</Text>}
            {!failed && !data && <Spinner size="xl" />}

            {data && (
                <>
                    <Box borderWidth="1px" borderRadius="lg" p={5}>
                        <Stack gap={4}>
                            <SimpleGrid columns={{ base: 1, md: 3 }} gap={4}>
                                <Stat label="Orçado" value={formatCents(data.totals.budgeted)} />
                                <Stat label="Gasto" value={formatCents(data.totals.spent)} />
                                <Stat
                                    label={data.totals.remaining < 0 ? "Estourou" : "Restante"}
                                    value={formatCents(Math.abs(data.totals.remaining))}
                                    color={data.totals.remaining < 0 ? "fg.error" : undefined}
                                />
                            </SimpleGrid>
                            <SpentBar spent={data.totals.spent} budgeted={data.totals.budgeted} label="Total gasto do orçamento do mês" />
                            {data.totals.budgeted === 0 && (
                                <Text color="fg.muted" fontSize="sm">
                                    Nada planejado para este mês. Digite um valor em uma categoria abaixo ou copie o mês anterior.
                                </Text>
                            )}
                            {data.totals.unbudgeted_spent > 0 && (
                                <Text color="fg.muted" fontSize="sm">
                                    Gasto em categorias sem orçamento: {formatCents(data.totals.unbudgeted_spent)}
                                </Text>
                            )}
                        </Stack>
                    </Box>

                    {data.groups.map((group) => (
                        <Box key={group.id} borderWidth="1px" borderRadius="lg" overflow="hidden">
                            <HStack
                                as="button"
                                w="full"
                                px={5}
                                py={3}
                                justify="space-between"
                                aria-expanded={isOpen(group)}
                                aria-label={`${group.name}: ${isOpen(group) ? "fechar" : "abrir"}`}
                                onClick={() => setOpened({ ...opened, [group.id]: !isOpen(group) })}
                                bg="bg.muted"
                                textAlign="left"
                            >
                                <HStack gap={3}>
                                    {isOpen(group) ? <LuChevronUp /> : <LuChevronDown />}
                                    <Text fontWeight="semibold">{group.name}</Text>
                                </HStack>
                                <Text fontSize="sm" color="fg.muted">
                                    {formatCents(group.spent)} de {formatCents(group.budgeted)}
                                </Text>
                            </HStack>

                            {isOpen(group) && (
                                <Stack as="ul" listStyleType="none" gap={0} aria-label={group.name}>
                                    {group.categories.map((category) => {
                                        const name = plainName(category.name);
                                        const { state } = budgetStatus(category.spent, category.budgeted);
                                        return (
                                            <Stack as="li" key={category.id} gap={2} px={5} py={3} borderTopWidth="1px">
                                                <HStack justify="space-between" gap={4} wrap="wrap">
                                                    <Text flex="1" minW="10rem">{category.name}</Text>
                                                    <Text fontSize="sm" color="fg.muted" aria-label={`Gasto em ${name}`}>
                                                        {formatCents(category.spent)} gastos
                                                    </Text>
                                                    <Input
                                                        size="sm"
                                                        w="9rem"
                                                        textAlign="right"
                                                        inputMode="numeric"
                                                        placeholder={maskAmount("0")}
                                                        aria-label={`Orçamento de ${name}`}
                                                        value={drafts[category.id] ?? asText(category.budgeted)}
                                                        onChange={(e) => setDrafts({ ...drafts, [category.id]: maskAmount(e.target.value) })}
                                                        onBlur={() => save(category)}
                                                        onKeyDown={(e) => e.key === "Enter" && e.currentTarget.blur()}
                                                    />
                                                </HStack>
                                                {category.budgeted > 0 && (
                                                    <>
                                                        <SpentBar spent={category.spent} budgeted={category.budgeted} label={`Gasto de ${name} no orçamento`} />
                                                        <HStack justify="space-between">
                                                            <Text fontSize="xs" color={state === "over" ? "fg.error" : "fg.muted"}>
                                                                {leftText(category.spent, category.budgeted)}
                                                            </Text>
                                                            {state === "over" && <Badge colorPalette="red">Acima do orçamento</Badge>}
                                                            {state === "warn" && <Badge colorPalette="orange">Perto do limite</Badge>}
                                                        </HStack>
                                                    </>
                                                )}
                                            </Stack>
                                        );
                                    })}
                                </Stack>
                            )}
                        </Box>
                    ))}
                </>
            )}
        </Stack>
    );
}
