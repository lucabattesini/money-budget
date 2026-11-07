import { Box, chakra, Link, Spinner, Stack, Text } from "@chakra-ui/react";
import { Link as RouterLink } from "react-router-dom";
import { budgetStatus, budgetsLink } from "../lib/budget";
import { useLocale } from "../lib/locale";
import { formatCents } from "../lib/money";
import DashboardCard from "./DashboardCard";

const Path = chakra.path; // (an upper case name, so the linter sees it used)
const COLORS = { ok: "green.500", warn: "orange.500", limit: "blue.500", over: "red.500", none: "gray.400" };
const ARC = "M 10 100 A 90 90 0 0 1 190 100"; // a half circle
const ARC_LENGTH = Math.PI * 90;

// How much is left to spend this month, as a half ring. `budget` is the answer of the budgets API for the month:
// undefined while it loads, null when it could not be loaded.
export default function BudgetRing({ budget, month }) {
    useLocale(); // amounts follow the family's currency
    const totals = budget?.totals;
    const planned = totals?.budgeted > 0;
    const { state, percent } = planned ? budgetStatus(totals.spent, totals.budgeted) : { state: "none", percent: 0 };
    const over = state === "over";

    let body;
    if (budget === undefined) {
        body = <Spinner />;
    } else if (budget === null) {
        body = <Text color="fg.muted">Não foi possível carregar os orçamentos.</Text>;
    } else if (!planned) {
        body = (
            <Text color="fg.muted">
                Nenhum orçamento definido para este mês.{" "}
                <Link as={RouterLink} to={budgetsLink(month)}>Definir orçamentos</Link>
            </Text>
        );
    } else {
        body = (
            <Stack align="center" gap={1}>
                <Box position="relative" w="full" maxW="18rem">
                    <svg viewBox="0 0 200 110" role="img" aria-label={`${percent}% do orçamento gasto`}>
                        <Path d={ARC} fill="none" stroke="border" strokeWidth="14" strokeLinecap="round" />
                        {percent > 0 && (
                            <Path
                                d={ARC}
                                fill="none"
                                stroke={COLORS[state]}
                                strokeWidth="14"
                                strokeLinecap="round"
                                strokeDasharray={`${(ARC_LENGTH * percent) / 100} ${ARC_LENGTH}`}
                            />
                        )}
                    </svg>
                    <Stack position="absolute" left={0} right={0} bottom={0} align="center" gap={0}>
                        <Text fontSize="2xl" fontWeight="bold" color={over ? "fg.error" : undefined}>
                            {formatCents(Math.abs(totals.remaining))}
                        </Text>
                        <Text fontSize="xs" color="fg.muted">{over ? "acima do orçamento" : "restantes"}</Text>
                    </Stack>
                </Box>
                <Text fontSize="sm" color="fg.muted">
                    {formatCents(totals.spent)} gastos de {formatCents(totals.budgeted)}
                </Text>
                {totals.unbudgeted_spent > 0 && (
                    <Text fontSize="xs" color="fg.muted">
                        + {formatCents(totals.unbudgeted_spent)} em categorias sem orçamento
                    </Text>
                )}
            </Stack>
        );
    }

    return (
        <DashboardCard title="Orçamento" to={budgetsLink(month)} linkText="Ver orçamentos">
            {body}
        </DashboardCard>
    );
}
