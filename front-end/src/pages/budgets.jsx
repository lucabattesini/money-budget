import PageHeading from "../components/PageHeading";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Badge, Box, Heading, HStack, IconButton, Input, InputGroup, Progress, SimpleGrid, Spinner, Stack, Text } from "@chakra-ui/react";
import { useSearchParams } from "react-router-dom";
import { LuChevronDown, LuChevronLeft, LuChevronRight, LuChevronUp, LuHistory, LuSearch } from "react-icons/lu";
import { getBudgets, setBudget } from "../api/endpoints";
import { getToken } from "../lib/auth";
import { budgetStatus, FIRST_MONTH, hasPlan, LAST_MONTH, monthFromLink, monthKey, monthLabel, shiftMonth } from "../lib/budget";
import { plainName } from "../lib/categoryName";
import { currencySymbol, familyNow, useLocale } from "../lib/locale";
import { budgetEditText, budgetFieldText, budgetTextToCents, formatBudgetCents, sanitizeBudgetText } from "../lib/money";
import { Tooltip } from "../components/ui/tooltip";
import customToaster from "../utils/customToaster";

const BAR_COLORS = { ok: "green", warn: "orange", limit: "blue", over: "red", none: "gray" };

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
            <Text fontSize="xs" color="fg.muted">{label}</Text>
            <Text fontSize={{ base: "md", md: "2xl" }} fontWeight="bold" color={color}>{value}</Text>
        </Stack>
    );
}

// What is left of a plan, or how much it was exceeded by
function leftText(spent, budgeted) {
    if (budgeted == null) return "";
    const left = budgeted - spent;
    if (left === 0) return "Dentro do orçamento: nada sobrando";
    return left > 0 ? `Restam ${formatBudgetCents(left)}` : `Estourou ${formatBudgetCents(-left)}`;
}

// One month of the family's plan: what is planned for each spending category, what was spent and what is left.
export default function Budgets() {
    const { timezone } = useLocale();
    const symbol = currencySymbol(); // amounts and the month name follow the family's currency and language
    const [params, setParams] = useSearchParams();
    // Opens on the month the link asks for (the dashboard sends the month it shows), this month otherwise
    // "This month" is read on the family's clock, again when its timezone arrives (the settings load after the first paint)
    // eslint-disable-next-line react-hooks/exhaustive-deps -- depends on the timezone only
    const thisMonth = useMemo(() => monthKey(familyNow()), [timezone]);
    // The month lives in the address (?month=2026-03), one history entry per month, so the back gesture goes to the month before
    const month = monthFromLink(params.get("month"), thisMonth);
    const setMonth = (key) => setParams(key === thisMonth ? {} : { month: key });
    const [data, setData] = useState(null);
    const [failed, setFailed] = useState(false);
    const [drafts, setDrafts] = useState({}); // what is being typed, by category id, until it is saved
    const [opened, setOpened] = useState({}); // groups the person closed (or opened again) by hand, by group id
    const shown = useRef(month); // an answer for a month that is no longer on the page must be ignored
    shown.current = month;
    const latest = useRef(0); // and so must an answer that a newer request has already replaced

    const load = useCallback(async (key) => {
        const token = getToken();
        if (!token) return;
        const mine = ++latest.current;
        const result = await getBudgets(key, token);
        if (shown.current !== key || latest.current !== mine) return;
        if (!result.ok) {
            setFailed(true);
            return;
        }
        setFailed(false);
        setData(result.data);
    }, []);

    useEffect(() => {
        setData(null);
        setFailed(false);
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
        const cents = budgetTextToCents(typed);
        const forMonth = month;
        if (cents === (category.budgeted ?? null)) {
            clearDraft(category.id);
            return;
        }
        const mine = ++latest.current;
        const result = await setBudget(category.id, forMonth, cents, getToken());
        if (!result.ok) {
            customToaster("Erro", "error", result.detail || "Não foi possível salvar o orçamento. Tente novamente.");
            clearDraft(category.id); // back to what is saved
            return;
        }
        clearDraft(category.id);
        if (shown.current !== forMonth || latest.current !== mine) return; // a newer answer already shows the month
        setData(result.data);
    };

    const [search, setSearch] = useState("");
    const searching = search.trim() !== "";
    const isOpen = (group) => searching || (opened[group.id] ?? true); // every group starts open; a search opens them all
    const fold = (text) => plainName(text).normalize("NFD").replace(/\p{M}/gu, "").toLowerCase(); // "Água" is found by "agua"
    const matches = (category) => fold(category.name).includes(fold(search));
    const groups = data ? (searching ? data.groups.map((g) => ({ ...g, categories: g.categories.filter(matches) })).filter((g) => g.categories.length > 0) : data.groups) : [];

    return (
        <Stack gap={6} maxW="5xl" mx="auto" px={{ base: 4, md: 6 }} pt={{ base: 6, md: 10 }} pb={12}>
            <PageHeading title="Orçamentos" size="2xl">
                Planeje quanto gastar em cada categoria e acompanhe o que já foi gasto. O valor de um mês vale para os
                meses seguintes até você mudar. Só entram as saídas de dinheiro.
            </PageHeading>

            <HStack gap={2} w="full">
                <IconButton aria-label="Mês anterior" variant="outline" size="sm" disabled={month <= FIRST_MONTH} onClick={() => setMonth(shiftMonth(month, -1))}>
                    <LuChevronLeft />
                </IconButton>
                <Heading size="lg" flex="1" textAlign="center" textTransform="capitalize" aria-live="polite">
                    {monthLabel(month)}
                </Heading>
                <IconButton aria-label="Próximo mês" variant="outline" size="sm" disabled={month >= LAST_MONTH} onClick={() => setMonth(shiftMonth(month, 1))}>
                    <LuChevronRight />
                </IconButton>
            </HStack>

            {failed && <Text color="fg.error">Não foi possível carregar o orçamento. Tente novamente mais tarde.</Text>}
            {!failed && !data && <Spinner size="xl" />}

            {data && (
                <>
                    <Box borderWidth="1px" borderRadius="lg" p={{ base: 3, md: 5 }}>
                        <Stack gap={{ base: 2, md: 4 }}>
                            <SimpleGrid columns={3} gap={{ base: 2, md: 4 }}>
                                <Stat label="Orçado" value={formatBudgetCents(data.totals.budgeted)} />
                                <Stat label="Gasto" value={formatBudgetCents(data.totals.spent)} />
                                <Stat
                                    label={data.totals.remaining < 0 ? "Estourou" : "Restante"}
                                    value={formatBudgetCents(Math.abs(data.totals.remaining))}
                                    color={data.totals.remaining < 0 ? "fg.error" : undefined}
                                />
                            </SimpleGrid>
                            {hasPlan(data) && <SpentBar spent={data.totals.spent} budgeted={data.totals.budgeted} label="Total gasto do orçamento do mês" />}
                            {!hasPlan(data) && (
                                <Text color="fg.muted" fontSize="sm">
                                    Nada planejado para este mês. Digite um valor em uma categoria abaixo: ele vale para este mês e os seguintes.
                                </Text>
                            )}
                            {data.totals.unbudgeted_spent > 0 && (
                                <Text color="fg.muted" fontSize="sm">
                                    Gasto em categorias sem orçamento: {formatBudgetCents(data.totals.unbudgeted_spent)}
                                </Text>
                            )}
                        </Stack>
                    </Box>

                    <InputGroup startElement={<LuSearch />}>
                        <Input
                            type="search"
                            aria-label="Buscar categoria"
                            placeholder="Buscar categoria"
                            minH="44px"
                            value={search}
                            onChange={(e) => setSearch(e.target.value)}
                        />
                    </InputGroup>
                    {searching && groups.length === 0 && <Text color="fg.muted">Nenhuma categoria encontrada.</Text>}

                    {groups.map((group) => (
                        <Box key={group.id} borderWidth="1px" borderRadius="lg" overflow="hidden">
                            <HStack
                                as="button"
                                w="full"
                                px={{ base: 4, md: 5 }}
                                py={3}
                                minH="44px"
                                justify="space-between"
                                wrap="wrap"
                                gap={1}
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
                                    {formatBudgetCents(group.spent)} de {formatBudgetCents(group.budgeted)}
                                </Text>
                            </HStack>

                            {isOpen(group) && (
                                <Stack as="ul" listStyleType="none" gap={0} aria-label={group.name}>
                                    {group.categories.map((category) => {
                                        const name = plainName(category.name);
                                        const { state } = budgetStatus(category.spent, category.budgeted);
                                        return (
                                            <Stack as="li" key={category.id} gap={2} px={{ base: 4, md: 5 }} py={3} borderTopWidth="1px">
                                                <HStack justify="space-between" gap={3}>
                                                    <Stack flex="1" minW={0} gap={1}>
                                                        <HStack gap={1.5}>
                                                            <Text>{category.name}</Text>
                                                            {category.budgeted != null && category.since && category.since !== month && (
                                                                <Tooltip content={`Repetido de ${monthLabel(category.since)}`} positioning={{ placement: "top" }}>
                                                                    <Box as="span" role="img" tabIndex={0} aria-label={`Repetido de ${monthLabel(category.since)}`} color="fg.muted" display="inline-flex">
                                                                        <LuHistory size={14} />
                                                                    </Box>
                                                                </Tooltip>
                                                            )}
                                                        </HStack>
                                                        {state === "over" && <Badge alignSelf="start" colorPalette="red">Acima do orçamento</Badge>}
                                                        {state === "warn" && <Badge alignSelf="start" colorPalette="orange">Perto do limite</Badge>}
                                                        {state === "limit" && <Badge alignSelf="start" colorPalette="blue">No limite</Badge>}
                                                    </Stack>
                                                    <InputGroup w={{ base: "8rem", sm: "10rem" }} startElement={<Text fontSize="sm" color="fg.muted">{symbol}</Text>}>
                                                        <Input
                                                            size="sm"
                                                            minH={{ base: "44px", md: "auto" }}
                                                            textAlign="right"
                                                            inputMode="decimal"
                                                            placeholder="0"
                                                            aria-label={`Orçamento de ${name}`}
                                                            value={drafts[category.id] ?? budgetFieldText(category.budgeted)}
                                                            onFocus={() => drafts[category.id] === undefined && setDrafts({ ...drafts, [category.id]: budgetEditText(category.budgeted) })}
                                                            onChange={(e) => setDrafts({ ...drafts, [category.id]: sanitizeBudgetText(e.target.value) })}
                                                            onBlur={() => save(category)}
                                                            onKeyDown={(e) => e.key === "Enter" && e.currentTarget.blur()}
                                                        />
                                                    </InputGroup>
                                                </HStack>
                                                {category.budgeted != null && <SpentBar spent={category.spent} budgeted={category.budgeted} label={`Gasto de ${name} no orçamento`} />}
                                                <HStack justify="space-between" align="start" gap={3}>
                                                    <Text fontSize="xs" color="fg.muted" aria-label={`Gasto em ${name}`}>
                                                        {formatBudgetCents(category.spent)} gastos
                                                    </Text>
                                                    {category.budgeted != null && (
                                                        <Text fontSize="xs" textAlign="right" color={state === "over" ? "fg.error" : "fg.muted"}>
                                                            {leftText(category.spent, category.budgeted)}
                                                        </Text>
                                                    )}
                                                </HStack>
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
