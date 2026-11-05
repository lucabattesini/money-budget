import { Fragment, useState, useEffect } from "react";
import { Center, Stack, Flex, Text, IconButton, Button, Box, Table, Menu, Popover, Portal } from "@chakra-ui/react";
import { useLocation } from "react-router-dom";
import { getTransactions, getAllCategories, deleteTransaction } from "../api/endpoints";
import { getToken } from "../lib/auth";
import { compareCategories } from "../lib/categoryName";
import { formatCents } from "../lib/money";
import { familyNow, formatDate, useLocale } from "../lib/locale";
import { applyFilters, countActiveFilters, filtersFromLink, hasActiveFilters } from "../lib/transactionFilters";
import customToaster from "../utils/customToaster";
import { SpinnerLoading } from "../components/spinnerLoading";
import TransactionSummary from "../components/TransactionSummary";
import TransactionDrawer from "../components/TransactionDrawer";
import TransactionFilters from "../components/TransactionFilters";
import { LuEllipsisVertical, LuListFilter, LuPencil, LuPlus, LuTrash2 } from "react-icons/lu";

// "Todo o Resto" can be long, so it is shown in pages
const PAGE_SIZE = 10;

export default function TransactionsDisplay() {
    useLocale(); // amounts and dates follow the family's currency and language
    const [loading, setLoading] = useState(true);
    const [categories, setCategories] = useState([]);
    const [transactions, setTransactions] = useState([]);
    const [trigger, setTrigger] = useState(0);
    const [adding, setAdding] = useState(false);
    const [editing, setEditing] = useState(null); // the transaction being edited
    const { search } = useLocation();
    // Opens with the filters the link asks for (the dashboard sends the month it shows)
    const [filters, setFilters] = useState(() => filtersFromLink(search));
    const [page, setPage] = useState(1);

    useEffect(() => {
        const token = getToken();
        Promise.all([
            getAllCategories(token),
            getTransactions({"organized_by": null, "date": null}, token)
        ]).then(([categoriesData, transactionsData]) => {
            // After an expired login the token is gone and the user is on the login page: no message there
            if ((!categoriesData || !transactionsData) && getToken()) {
                customToaster("Error", "error", "Não foi possível carregar suas transações. Tente novamente mais tarde.");
            }
            if (categoriesData) setCategories(categoriesData.data);
            if (transactionsData) setTransactions(transactionsData.data);
            setLoading(false);
        });
    }, [trigger]);

    // Alphabetical, so categories are easy to find in every list
    const sortedCategories = [...categories].sort(compareCategories);

    const changeFilters = (next) => {
        setFilters(next);
        setPage(1);
    };

    const reload = () => setTrigger((current) => current + 1);

    // Wait for the delete to finish before reloading, otherwise the list can still show the row
    const onDelete = async (id) => {
        const response = await deleteTransaction(id, getToken());
        if (!response || !response.ok) {
            customToaster("Erro", "error", "Não foi possível excluir a transação.");
        }
        reload();
    }

    const today = [];
    const thisWeek = [];
    const thisMonth = [];
    const older = [];

    const now = familyNow();
    // Start of today
    const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    
    // Start of this week (last 7 days)
    const startOfWeek = new Date(startOfToday);
    startOfWeek.setDate(startOfWeek.getDate() - 7);

    // Start of this month
    const startOfMonth = new Date(now.getFullYear(), now.getMonth(), 1);

    const filtered = applyFilters(transactions, filters);
    const activeFilters = countActiveFilters(filters);

    filtered.forEach(transaction => {
        const tDate = new Date(transaction.transactioned_at);
        if (tDate >= startOfToday) {
            today.push(transaction);
        } else if (tDate >= startOfWeek) {
            thisWeek.push(transaction);
        } else if (tDate >= startOfMonth) {
            thisMonth.push(transaction);
        } else {
            older.push(transaction);
        }
    });

    const groups = [
        { title: "Hoje", data: today },
        { title: "Esta Semana", data: thisWeek },
        { title: "Este Mês", data: thisMonth },
        { title: "Todo o Resto", data: older },
    ];

    const categoryName = (transaction) =>
        categories?.find((category) => category.id === transaction.category_id)?.name ?? "Categoria não encontrada";

    const renderRow = (transaction) => (
        <Table.Row key={transaction.id} cursor="pointer" _hover={{ bg: "bg.muted" }} onClick={() => setEditing(transaction)}>
            <Table.Cell whiteSpace="nowrap">{formatDate(transaction.transactioned_at)}</Table.Cell>
            <Table.Cell wordBreak="break-word">{transaction.label}</Table.Cell>
            <Table.Cell color="fg.muted">{categoryName(transaction)}</Table.Cell>
            <Table.Cell textAlign="end" whiteSpace="nowrap" color={transaction.type === "credit" ? "green.400" : undefined}>
                {transaction.type === "credit" ? "+" : "-"} {formatCents(transaction.value)}
            </Table.Cell>
            {/* Clicks here (the menu is rendered elsewhere but still bubbles) must not open the editor */}
            <Table.Cell textAlign="end" width="1%" onClick={(event) => event.stopPropagation()}>
                <Menu.Root positioning={{ placement: "bottom-end" }}>
                    <Menu.Trigger asChild>
                        <IconButton variant="ghost" size="xs" aria-label={`Ações para ${transaction.label}`}>
                            <LuEllipsisVertical />
                        </IconButton>
                    </Menu.Trigger>
                    <Portal>
                        <Menu.Positioner>
                            <Menu.Content>
                                <Menu.Item value="edit" onClick={() => setEditing(transaction)}>
                                    <LuPencil /> Editar
                                </Menu.Item>
                                <Menu.Item value="delete" color="fg.error" onClick={() => onDelete(transaction.id)}>
                                    <LuTrash2 /> Excluir
                                </Menu.Item>
                            </Menu.Content>
                        </Menu.Positioner>
                    </Portal>
                </Menu.Root>
            </Table.Cell>
        </Table.Row>
    );

    // Only the oldest group is paginated
    const pageCount = Math.max(1, Math.ceil(older.length / PAGE_SIZE));
    const currentPage = Math.min(page, pageCount);
    const visibleGroups = groups
        .map((group) => group.data === older
            ? { ...group, data: older.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE) }
            : group)
        .filter((group) => group.data.length > 0);

    return(
        <Center>
            <Stack minHeight="100vh" gap={6} w="full" maxW="4xl" align="center" justify="flex-start" py={10} px={4}>
                <TransactionSummary transactions={transactions} />

                <Flex w="full" justify="space-between" align="center">
                    <Text fontSize="lg" fontWeight="bold">Transações</Text>
                    <Flex gap={2}>
                        <Popover.Root lazyMount unmountOnExit positioning={{ placement: "bottom-end" }}>
                            <Popover.Trigger asChild>
                                <Button size="sm" variant="outline">
                                    <LuListFilter /> Filtros{activeFilters > 0 ? ` (${activeFilters})` : ""}
                                </Button>
                            </Popover.Trigger>
                            <Portal>
                                <Popover.Positioner>
                                    <Popover.Content width="auto">
                                        <Popover.Body>
                                            <TransactionFilters
                                                filters={filters}
                                                onChange={changeFilters}
                                                categories={sortedCategories}
                                            />
                                        </Popover.Body>
                                    </Popover.Content>
                                </Popover.Positioner>
                            </Portal>
                        </Popover.Root>
                        <Button size="sm" onClick={() => setAdding(true)}>
                            <LuPlus /> Adicionar
                        </Button>
                    </Flex>
                </Flex>

                {loading && <SpinnerLoading/>}

                {!loading && visibleGroups.length > 0 && (
                    <Table.ScrollArea w="full">
                        <Table.Root size="sm">
                            <Table.Body>
                                {visibleGroups.map((group) => (
                                    <Fragment key={group.title}>
                                        <Table.Row>
                                            <Table.Cell colSpan={5} pt={6}>
                                                <Box color="gray.400" fontSize="xs" fontWeight="bold" textTransform="uppercase">
                                                    {group.title}
                                                </Box>
                                            </Table.Cell>
                                        </Table.Row>
                                        {group.data.map(renderRow)}
                                    </Fragment>
                                ))}
                            </Table.Body>
                        </Table.Root>
                    </Table.ScrollArea>
                )}

                {!loading && pageCount > 1 && (
                    <Flex align="center" gap={3}>
                        <Button size="xs" variant="outline" disabled={currentPage === 1}
                            onClick={() => setPage(currentPage - 1)}>
                            Anterior
                        </Button>
                        <Text fontSize="sm">Página {currentPage} de {pageCount}</Text>
                        <Button size="xs" variant="outline" disabled={currentPage === pageCount}
                            onClick={() => setPage(currentPage + 1)}>
                            Próxima
                        </Button>
                    </Flex>
                )}

                {!loading && filtered.length === 0 && (
                    <Text color="fg.muted">
                        {hasActiveFilters(filters) ? "Nenhuma transação encontrada com esses filtros." : "Nenhuma transação ainda."}
                    </Text>
                )}
            </Stack>

            <TransactionDrawer
                open={adding}
                onClose={() => setAdding(false)}
                categories={sortedCategories}
                onSaved={reload}
            />
            <TransactionDrawer
                open={editing !== null}
                transaction={editing}
                onClose={() => setEditing(null)}
                categories={sortedCategories}
                onSaved={reload}
            />
        </Center>
    )
}
