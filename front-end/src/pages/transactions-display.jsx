import { Fragment, useState, useEffect } from "react";
import { Badge, Center, Stack, Flex, Text, IconButton, Button, Box, Table, Menu, Popover, Portal, Checkbox } from "@chakra-ui/react";
import { useLocation } from "react-router-dom";
import { getTransactions, getAllCategories, getFamily, getMerchants, deleteTransaction } from "../api/endpoints";
import { getToken } from "../lib/auth";
import { compareCategories } from "../lib/categoryName";
import { formatCents } from "../lib/money";
import { familyNow, formatDate, setLocale, useLocale } from "../lib/locale";
import { applyFilters, countActiveFilters, filtersFromLink, hasActiveFilters } from "../lib/transactionFilters";
import customToaster from "../utils/customToaster";
import { SpinnerLoading } from "../components/spinnerLoading";
import TransactionSummary from "../components/TransactionSummary";
import TransactionDrawer from "../components/TransactionDrawer";
import TransactionFilters from "../components/TransactionFilters";
import { BulkDeleteDialog, BulkEditDialog } from "../components/BulkActions";
import PersonAvatar from "../components/PersonAvatar";
import MerchantTotals from "../components/MerchantTotals";
import { LuEllipsisVertical, LuListFilter, LuPencil, LuPlus, LuTrash2 } from "react-icons/lu";

// "Todo o Resto" can be long, so it is shown in pages
const PAGE_SIZE = 30;

export default function TransactionsDisplay() {
    const { merchantsEnabled } = useLocale(); // amounts and dates follow the family's currency and language
    const [merchants, setMerchants] = useState(null); // null: off, or the list could not be loaded (an edit must not touch merchants then)
    const [loading, setLoading] = useState(true);
    const [categories, setCategories] = useState([]);
    const [transactions, setTransactions] = useState([]);
    const [family, setFamily] = useState({ members: [], me: null }); // who can be chosen, and who is logged in
    const [trigger, setTrigger] = useState(0);
    const [adding, setAdding] = useState(false);
    const [editing, setEditing] = useState(null); // the transaction being edited
    const { search } = useLocation();
    // Opens with the filters the link asks for (the dashboard sends the month it shows)
    const [filters, setFilters] = useState(() => filtersFromLink(search));
    const [page, setPage] = useState(1);
    const [selected, setSelected] = useState(() => new Set()); // ids of the rows ticked
    const [bulkEditing, setBulkEditing] = useState(false);
    const [bulkDeleting, setBulkDeleting] = useState(false);

    useEffect(() => {
        const token = getToken();
        Promise.all([
            getAllCategories(token),
            getTransactions({"organized_by": null, "date": null}, token),
            getFamily(token)
        ]).then(async ([categoriesData, transactionsData, familyResult]) => {
            // After an expired login the token is gone and the user is on the login page: no message there
            if ((!categoriesData || !transactionsData) && getToken()) {
                customToaster("Error", "error", "Não foi possível carregar suas transações. Tente novamente mais tarde.");
            }
            if (categoriesData) setCategories(categoriesData.data);
            if (transactionsData) setTransactions(transactionsData.data);
            // Without the family the page still works: rows just show no picture
            if (familyResult?.ok) setLocale(familyResult.data); // the merchants switch
            if (familyResult?.ok && familyResult.data.merchants_enabled) {
                const merchantsResult = await getMerchants(token);
                setMerchants(merchantsResult.ok ? merchantsResult.data : null);
            } else {
                setMerchants(null);
            }
            if (familyResult?.ok) setFamily({ members: familyResult.data.members ?? [], me: familyResult.data.me ?? null });
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

    const toggle = (id, on) => setSelected((current) => {
        const next = new Set(current);
        if (on) next.add(id); else next.delete(id);
        return next;
    });
    // After changing or deleting many: nothing stays ticked, and the list is read again
    const afterBulk = () => {
        setBulkEditing(false);
        setBulkDeleting(false);
        setSelected(new Set());
        reload();
    };

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
    // A row that the filters now hide is not acted on, even if it was ticked before
    const selectedIds = filtered.filter((transaction) => selected.has(transaction.id)).map((transaction) => transaction.id);
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

    const merchantName = (transaction) => merchants?.find((merchant) => merchant.id === transaction.merchant_id)?.name;

    // A category name starts with its emoji ("🎁 Presentes"); the phone layout shows the icon and the name apart
    const categoryParts = (name) => {
        const first = [...new Intl.Segmenter().segment(name)][0]?.segment ?? ""; // one whole emoji, flags and joined emoji included
        return /^(\p{Extended_Pictographic}|\p{Regional_Indicator})/u.test(first) ? { icon: first, name: name.slice(first.length).trim() } : { icon: "", name };
    };

    const renderRow = (transaction) => (
        <Table.Row
            key={transaction.id}
            cursor="pointer"
            _hover={{ bg: "bg.muted" }}
            onClick={() => setEditing(transaction)}
            // On a phone each row is a small card: the category icon on the left, description above "category · first name", amount on the right
            display={{ base: "grid", md: "table-row" }}
            gridTemplateColumns="32px 36px auto auto minmax(0, 1fr) auto 44px"
            gridTemplateAreas={'"check icon label label label amount menu" "check icon category person . amount menu"'}
            alignItems="center"
            columnGap={2}
            py={{ base: 1, md: 0 }}
            borderBottomWidth={{ base: "1px", md: 0 }}
        >
            {/* Ticking a row must not open the editor */}
            <Table.Cell gridArea="check" width="1%" pr={0} borderBottomWidth={{ base: 0, md: "1px" }} onClick={(event) => event.stopPropagation()}>
                <Checkbox.Root
                    checked={selected.has(transaction.id)}
                    onCheckedChange={(e) => toggle(transaction.id, Boolean(e.checked))}
                >
                    <Checkbox.HiddenInput aria-label={`Selecionar ${transaction.label}`} />
                    <Checkbox.Control />
                </Checkbox.Root>
            </Table.Cell>
            <Table.Cell hideBelow="md" whiteSpace="nowrap" gridArea="date" fontSize={{ base: "xs", md: "sm" }} color={{ base: "fg.muted", md: "fg" }} borderBottomWidth={{ base: 0, md: "1px" }} py={{ base: 1, md: 2 }}>{formatDate(transaction.transactioned_at)}</Table.Cell>
            <Table.Cell wordBreak="break-word" minW={0} gridArea="label" pr={{ base: 3, md: 2 }} borderBottomWidth={{ base: 0, md: "1px" }} pb={{ base: 0, md: 2 }}>
                {transaction.label}
                {transaction.excluded && (
                    <Badge ml={2} size="xs" variant="subtle" colorPalette="gray" title="Não conta nos totais">Fora dos totais</Badge>
                )}
                {merchantsEnabled && merchantName(transaction) && (
                    <Text fontSize="xs" color="fg.muted">{merchantName(transaction)}</Text>
                )}
            </Table.Cell>
            <Table.Cell color="fg.muted" gridArea="category" fontSize={{ base: "xs", md: "sm" }} minW={0} pr={{ base: 0, md: 3 }} borderBottomWidth={{ base: 0, md: "1px" }} py={{ base: 1, md: 2 }}>
                {categoryParts(categoryName(transaction)).icon && <Text as="span" hideBelow="md">{categoryParts(categoryName(transaction)).icon} </Text>}{categoryParts(categoryName(transaction)).name}
            </Table.Cell>
            {/* Phone: the first name after the category; larger screens: the picture */}
            <Table.Cell width="1%" gridArea="person" justifySelf="start" whiteSpace="nowrap" px={{ base: 0, md: 3 }} fontSize="xs" color="fg.muted" borderBottomWidth={{ base: 0, md: "1px" }} py={{ base: 1, md: 2 }}>
                {(() => {
                    const person = family.members.find((member) => member.id === transaction.user_id);
                    return person && (<>
                        <Box hideBelow="md"><PersonAvatar person={person} /></Box>
                        <Text as="span" hideFrom="md" ml={2}>· {person.name.split(" ")[0]}</Text>
                    </>);
                })()}
            </Table.Cell>
            <Table.Cell textAlign="end" whiteSpace="nowrap" gridArea="amount" borderBottomWidth={{ base: 0, md: "1px" }} pb={{ base: 0, md: 2 }} color={transaction.type === "credit" ? "green.400" : undefined}>
                {transaction.type === "credit" ? "+" : "-"} {formatCents(transaction.value)}
            </Table.Cell>
            {/* Clicks here (the menu is rendered elsewhere but still bubbles) must not open the editor */}
            <Table.Cell textAlign="end" width="1%" gridArea="menu" borderBottomWidth={{ base: 0, md: "1px" }} onClick={(event) => event.stopPropagation()}>
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
            {/* Phone only (last in the row so the table columns keep their places): the category's icon (the emoji its name starts with) */}
            <Table.Cell hideFrom="md" gridArea="icon" fontSize="xl" textAlign="center" p={0} borderBottomWidth={0} aria-hidden="true">{categoryParts(categoryName(transaction)).icon}</Table.Cell>
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

    const shownIds = visibleGroups.flatMap((group) => group.data.map((transaction) => transaction.id));
    const allShownTicked = shownIds.length > 0 && shownIds.every((id) => selected.has(id));

    return(
        <Center>
            <Stack gap={6} w="full" maxW={{ base: "4xl", md: "7xl" }} align="center" justify="flex-start" py={{ base: 6, md: 10 }} px={4}>
                <TransactionSummary transactions={transactions} />

                {merchantsEnabled && merchants && <MerchantTotals transactions={filtered} merchants={merchants} />}

                <Flex w="full" justify="space-between" align="center" wrap="wrap" gap={2}>
                    <Text fontSize="lg" fontWeight="bold">Transações</Text>
                    <Flex gap={2}>
                        <Popover.Root lazyMount unmountOnExit positioning={{ placement: "bottom-end" }}>
                            <Popover.Trigger asChild>
                                <Button size="sm" variant="outline" minH={{ base: "44px", md: "auto" }}>
                                    <LuListFilter /> Filtros{activeFilters > 0 ? ` (${activeFilters})` : ""}
                                </Button>
                            </Popover.Trigger>
                            <Portal>
                                <Popover.Positioner>
                                    <Popover.Content width="auto" maxW="calc(100vw - 2rem)" maxH="calc(100dvh - 8rem)" overflowY="auto">
                                        <Popover.Body>
                                            <TransactionFilters
                                                filters={filters}
                                                onChange={changeFilters}
                                                categories={sortedCategories}
                                                members={family.members}
                                                merchants={merchants ?? []}
                                            />
                                        </Popover.Body>
                                    </Popover.Content>
                                </Popover.Positioner>
                            </Portal>
                        </Popover.Root>
                        <Button size="sm" minH={{ base: "44px", md: "auto" }} onClick={() => setAdding(true)}>
                            <LuPlus /> Adicionar
                        </Button>
                    </Flex>
                </Flex>

                {selectedIds.length > 0 && (
                    <Flex w="full" align="center" justify="space-between" wrap="wrap" gap={2} p={3} borderWidth="1px" borderRadius="md" bg="bg.muted" role="region" aria-label="Ações para as selecionadas">
                        <Text fontSize="sm" fontWeight="semibold" role="status">
                            {selectedIds.length === 1 ? "1 selecionada" : `${selectedIds.length} selecionadas`}
                        </Text>
                        <Flex gap={2} wrap="wrap">
                            <Button size="sm" variant="outline" onClick={() => setSelected(new Set())}>Limpar seleção</Button>
                            <Button size="sm" onClick={() => setBulkEditing(true)}><LuPencil /> Editar selecionadas</Button>
                            <Button size="sm" colorPalette="red" variant="outline" onClick={() => setBulkDeleting(true)}><LuTrash2 /> Excluir selecionadas</Button>
                        </Flex>
                    </Flex>
                )}

                {!loading && shownIds.length > 0 && (
                    <Flex w="full">
                        <Checkbox.Root
                            checked={allShownTicked}
                            onCheckedChange={(e) => setSelected((current) => {
                                const next = new Set(current);
                                shownIds.forEach((id) => (e.checked ? next.add(id) : next.delete(id)));
                                return next;
                            })}
                        >
                            <Checkbox.HiddenInput />
                            <Checkbox.Control />
                            <Checkbox.Label fontSize="sm">Selecionar todas as exibidas</Checkbox.Label>
                        </Checkbox.Root>
                    </Flex>
                )}

                {loading && <SpinnerLoading/>}

                {!loading && visibleGroups.length > 0 && (
                    <Table.ScrollArea w="full" overflowX="hidden" borderWidth={0}>
                        <Table.Root size="sm" w="full" display={{ base: "block", md: "table" }}>
                            <Table.Body display={{ base: "block", md: "table-row-group" }}>
                                {visibleGroups.map((group) => (
                                    <Fragment key={group.title}>
                                        <Table.Row display={{ base: "block", md: "table-row" }}>
                                            <Table.Cell colSpan={7} pt={6} display={{ base: "block", md: "table-cell" }}>
                                                <Box color="gray.400" fontSize="xs" fontWeight="bold" textTransform="uppercase">
                                                    {group.title}
                                                </Box>
                                            </Table.Cell>
                                        </Table.Row>
                                        {group.data.map((transaction, index) => (
                                            <Fragment key={transaction.id}>
                                                {/* Phone only: the rows are grouped under their day, so the row itself does not show the date */}
                                                {transaction.transactioned_at.slice(0, 10) !== group.data[index - 1]?.transactioned_at.slice(0, 10) && (
                                                    <Table.Row data-day hideFrom="md" display="block">
                                                        <Table.Cell display="block" pt={3} pb={1} px="10px" borderBottomWidth={0} color="fg.muted" fontSize="xs" fontWeight="semibold">
                                                            {formatDate(transaction.transactioned_at)}
                                                        </Table.Cell>
                                                    </Table.Row>
                                                )}
                                                {renderRow(transaction)}
                                            </Fragment>
                                        ))}
                                    </Fragment>
                                ))}
                            </Table.Body>
                        </Table.Root>
                    </Table.ScrollArea>
                )}

                {!loading && pageCount > 1 && (
                    <Flex align="center" gap={3}>
                        <Button size={{ base: "sm", md: "xs" }} variant="outline" disabled={currentPage === 1}
                            onClick={() => setPage(currentPage - 1)}>
                            Anterior
                        </Button>
                        <Text fontSize="sm">Página {currentPage} de {pageCount}</Text>
                        <Button size={{ base: "sm", md: "xs" }} variant="outline" disabled={currentPage === pageCount}
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

            <BulkEditDialog
                ids={selectedIds}
                open={bulkEditing}
                onClose={() => setBulkEditing(false)}
                categories={sortedCategories}
                members={family.members}
                merchants={merchantsEnabled ? merchants : null}
                onDone={afterBulk}
            />
            <BulkDeleteDialog ids={selectedIds} open={bulkDeleting} onClose={() => setBulkDeleting(false)} onDone={afterBulk} />
            <TransactionDrawer
                open={adding}
                onClose={() => setAdding(false)}
                categories={sortedCategories}
                members={family.members}
                me={family.me}
                merchants={merchantsEnabled ? merchants : null}
                onSaved={reload}
            />
            <TransactionDrawer
                open={editing !== null}
                transaction={editing}
                onClose={() => setEditing(null)}
                categories={sortedCategories}
                members={family.members}
                me={family.me}
                merchants={merchantsEnabled ? merchants : null}
                onSaved={reload}
            />
        </Center>
    )
}
