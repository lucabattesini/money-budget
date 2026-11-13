import { Fragment, useState, useEffect, useMemo, useRef } from "react";
import { Center, Stack, Flex, Text, IconButton, Button, Box, Table, Menu, Popover, Portal, Checkbox } from "@chakra-ui/react";
import { useLocation, useSearchParams } from "react-router-dom";
import useBackClosesOverlay from "../lib/useBackClosesOverlay";
import { getTransactions, getAllCategories, getFamily, getMerchants, deleteTransaction, updateTransaction } from "../api/endpoints";
import { getToken } from "../lib/auth";
import { compareCategories } from "../lib/categoryName";
import { formatCents } from "../lib/money";
import { formatDate, setLocale, useLocale } from "../lib/locale";
import { applyFilters, countActiveFilters, filtersFromLink, hasActiveFilters, writeFilters } from "../lib/transactionFilters";
import customToaster from "../utils/customToaster";
import { SpinnerLoading } from "../components/spinnerLoading";
import TransactionSummary from "../components/TransactionSummary";
import TransactionDrawer from "../components/TransactionDrawer";
import CategoryPicker from "../components/CategoryPicker";
import TransactionFilters from "../components/TransactionFilters";
import { BulkDeleteDialog, BulkEditDialog } from "../components/BulkActions";
import PersonAvatar from "../components/PersonAvatar";
import { LuEllipsisVertical, LuListChecks, LuListFilter, LuPencil, LuPlus, LuTrash2 } from "react-icons/lu";

// The list is one long list that fills in as it is scrolled: this many rows more each time the end comes near
const BATCH = 40;

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
    const { search, state: routeState } = useLocation(); // routeState carries the open panels (see useBackClosesOverlay): every change of the address keeps it
    // Opens with the filters the link asks for (the dashboard sends the month it shows)
    const [filters, setFilters] = useState(() => filtersFromLink(search));
    const [params, setParams] = useSearchParams();
    const [visibleCount, setVisibleCount] = useState(BATCH); // how many rows of the list are on the page so far
    const [selecting, setSelecting] = useState(false); // the tick boxes only show in selection mode
    const [selected, setSelected] = useState(() => new Set()); // ids of the rows ticked
    const [filtersOpen, setFiltersOpen] = useState(false);
    useBackClosesOverlay(filtersOpen, () => setFiltersOpen(false)); // and closes the filter panel
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
    const sortedCategories = useMemo(() => [...categories].sort(compareCategories), [categories]);

    const changeFilters = (next) => {
        setFilters(next);
        setVisibleCount(BATCH); // a new search starts from the top
    };

    // The filters are in the address too (reload or share the page and they stay), written over the entry, not one entry per
    // keystroke. The page's own state is the truth: when the address differs (closing the filter panel steps back to the
    // entry from before it opened), it is written again.
    useEffect(() => {
        const written = writeFilters(params, filters);
        const same = (a, b) => [...a].sort().join("&") === [...b].sort().join("&");
        if (same(written.entries(), params.entries())) return;
        setParams(written, { replace: true, state: routeState });
        // eslint-disable-next-line react-hooks/exhaustive-deps -- when the filters or the address change
    }, [filters, search]);

    const reload = () => setTrigger((current) => current + 1);

    // Fix a wrong category right from the list. The server takes the whole transaction, so what it already has is sent back
    // as it is (no date, type, person, merchant or excluded: those stay as they are); the list is loaded again after.
    const [changingCategory, setChangingCategory] = useState(null); // the id of the transaction being saved
    const [pickerFor, setPickerFor] = useState(null); // the id of the row whose category is being changed
    const changeCategory = async (transaction, categoryId) => {
        if (!categoryId || categoryId === String(transaction.category_id)) return;
        setChangingCategory(transaction.id);
        const result = await updateTransaction(transaction.id, { label: transaction.label, value: transaction.value, category_id: categoryId }, getToken());
        setChangingCategory(null);
        if (result && (result.status === 200 || result.status === 201)) {
            customToaster("Salvo", "success", "A categoria foi atualizada!");
            reload();
        } else {
            customToaster("Erro", "error", "Não foi possível trocar a categoria. Tente novamente.");
        }
    };

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
        setSelecting(false);
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

    // One list, newest first
    // (dates are written year first, so comparing the text is comparing the times; equal ones keep the server's order)
    const filtered = useMemo(
        () => applyFilters(transactions, filters).sort((a, b) => (a.transactioned_at < b.transactioned_at ? 1 : a.transactioned_at > b.transactioned_at ? -1 : 0)),
        [transactions, filters],
    );
    // A row that the filters now hide is not acted on, even if it was ticked before
    const MAX_BULK = 500; // what the server accepts in one request
    const selectedIds = filtered.filter((transaction) => selected.has(transaction.id)).map((transaction) => transaction.id);
    const activeFilters = countActiveFilters(filters);

    // The rows are all here already; only some are put on the page, and more as the end of the list comes into view
    const visible = filtered.slice(0, visibleCount);
    const hasMore = visibleCount < filtered.length;
    const canObserve = typeof IntersectionObserver !== "undefined";
    const end = useRef(null);
    useEffect(() => {
        if (!hasMore || !canObserve || !end.current || typeof IntersectionObserver === "undefined") return undefined;
        // Looked at again after every batch: if the end is still in view, the next batch comes at once
        const watcher = new IntersectionObserver((entries) => {
            if (entries.some((entry) => entry.isIntersecting)) setVisibleCount((count) => count + BATCH);
        }, { rootMargin: "600px" });
        watcher.observe(end.current);
        return () => watcher.disconnect();
    }, [hasMore, canObserve, visibleCount]);

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
            onClick={() => (selecting ? toggle(transaction.id, !selected.has(transaction.id)) : setEditing(transaction))} // in selection mode a click ticks the row instead of opening the editor
            // On a phone each row is a small card: the category icon on the left, description above "category · first name", amount on the right
            display={{ base: "grid", md: "table-row" }}
            gridTemplateColumns={selecting ? "32px 36px auto auto minmax(0, 1fr) auto 44px" : "36px auto auto minmax(0, 1fr) auto 44px"}
            gridTemplateAreas={selecting
                ? '"check icon label label label amount menu" "check icon category person . amount menu"'
                : '"icon label label label amount menu" "icon category person . amount menu"'}
            alignItems="center"
            columnGap={2}
            py={{ base: 1, md: 0 }}
            borderBottomWidth={{ base: "1px", md: 0 }}
        >
            {/* Ticking a row must not open the editor */}
            {selecting && (
                <Table.Cell gridArea="check" width="1%" pr={0} borderBottomWidth={{ base: 0, md: "1px" }} onClick={(event) => event.stopPropagation()}>
                    <Checkbox.Root
                        checked={selected.has(transaction.id)}
                        onCheckedChange={(e) => toggle(transaction.id, Boolean(e.checked))}
                    >
                        <Checkbox.HiddenInput aria-label={`Selecionar ${transaction.label}`} />
                        <Checkbox.Control />
                    </Checkbox.Root>
                </Table.Cell>
            )}
            <Table.Cell hideBelow="md" whiteSpace="nowrap" gridArea="date" fontSize={{ base: "xs", md: "sm" }} color={{ base: "fg.muted", md: "fg" }} borderBottomWidth={{ base: 0, md: "1px" }} py={{ base: 1, md: 2 }}>{formatDate(transaction.transactioned_at)}</Table.Cell>
            <Table.Cell wordBreak="break-word" minW={0} gridArea="label" pr={{ base: 3, md: 2 }} borderBottomWidth={{ base: 0, md: "1px" }} pb={{ base: 0, md: 2 }}>
                {transaction.label}
                {merchantsEnabled && merchantName(transaction) && (
                    <Text fontSize="xs" color="fg.muted">{merchantName(transaction)}</Text>
                )}
            </Table.Cell>
            <Table.Cell color="fg.muted" gridArea="category" fontSize={{ base: "xs", md: "sm" }} minW={0} pr={{ base: 0, md: 3 }} borderBottomWidth={{ base: 0, md: "1px" }} py={{ base: 1, md: 2 }}>
                {selecting ? (
                    <>
                        {categoryParts(categoryName(transaction)).icon && <Text as="span" hideBelow="md">{categoryParts(categoryName(transaction)).icon} </Text>}{categoryParts(categoryName(transaction)).name}
                    </>
                ) : (
                    // Clicking the category opens the list right here; it must not open the editor of the row.
                    // Only the row being changed has the search box: one in every row made a long list slow to put on the page.
                    pickerFor === transaction.id ? (
                        <Box minW={{ base: "9rem", md: "12rem" }} onClick={(event) => event.stopPropagation()}>
                            <CategoryPicker
                                variant="inline"
                                defaultOpen
                                autoFocus
                                categories={sortedCategories}
                                value={String(transaction.category_id ?? "")}
                                onChange={(id) => changeCategory(transaction, id)}
                                onClosed={() => setPickerFor(null)}
                                disabled={changingCategory === transaction.id}
                                placeholder={categories.some((category) => category.id === transaction.category_id) ? "Sem categoria" : "Categoria não encontrada"}
                                aria-label={`Categoria de ${transaction.label}`}
                            />
                        </Box>
                    ) : (
                        <Text
                            as="button"
                            type="button"
                            textAlign="left"
                            cursor="pointer"
                            px={2}
                            py={1}
                            rounded="md"
                            _hover={{ bg: "bg.muted" }}
                            aria-label={`Trocar a categoria de ${transaction.label} (${categoryParts(categoryName(transaction)).name})`}
                            onClick={(event) => { event.stopPropagation(); setPickerFor(transaction.id); }}
                        >
                            {categoryParts(categoryName(transaction)).icon && <Text as="span" hideBelow="md">{categoryParts(categoryName(transaction)).icon} </Text>}{categoryParts(categoryName(transaction)).name}
                        </Text>
                    )
                )}
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
            <Table.Cell textAlign="end" whiteSpace="nowrap" gridArea="amount" borderBottomWidth={{ base: 0, md: "1px" }} pb={{ base: 0, md: 2 }} color={transaction.type === "credit" ? "green.400" : undefined} opacity={transaction.excluded ? 0.45 : 1} title={transaction.excluded ? "Não conta nos totais" : undefined}>
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

    const shownIds = visible.map((transaction) => transaction.id);
    const allShownTicked = shownIds.length > 0 && shownIds.every((id) => selected.has(id));

    return(
        <Center>
            <Stack gap={6} w="full" maxW={{ base: "4xl", md: "7xl" }} align="center" justify="flex-start" py={{ base: 6, md: 10 }} px={4}>
                <TransactionSummary transactions={transactions} />

                <Flex w="full" justify="space-between" align="center" wrap="wrap" gap={2}>
                    <Text fontSize="lg" fontWeight="bold">Transações</Text>
                    <Flex gap={2}>
                        <Popover.Root lazyMount unmountOnExit positioning={{ placement: "bottom-end" }} open={filtersOpen} onOpenChange={(e) => setFiltersOpen(e.open)}>
                            <Popover.Trigger asChild>
                                <Button size="sm" variant="outline" h={{ base: "44px", md: "9" }}>
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
                        <Button size="sm" variant={selecting ? "solid" : "outline"} h={{ base: "44px", md: "9" }} onClick={() => { setSelecting(!selecting); setSelected(new Set()); }}>
                            <LuListChecks /> {selecting ? "Cancelar" : "Selecionar"}
                        </Button>
                        <Button size="sm" h={{ base: "44px", md: "9" }} onClick={() => setAdding(true)}>
                            <LuPlus /> Adicionar
                        </Button>
                    </Flex>
                </Flex>

                {selecting && !loading && shownIds.length > 0 && (
                    <Flex w="full" align="center" justify="space-between" wrap="wrap" gap={2} p={3} borderWidth="1px" borderRadius="md" bg="bg.muted" role="region" aria-label="Ações para as selecionadas">
                        <Flex align="center" gap={4} wrap="wrap">
                            <Checkbox.Root
                                cursor="pointer"
                                checked={allShownTicked}
                                onCheckedChange={(e) => setSelected((current) => {
                                    const next = new Set(current);
                                    shownIds.forEach((id) => (e.checked ? next.add(id) : next.delete(id)));
                                    return next;
                                })}
                            >
                                <Checkbox.HiddenInput />
                                <Checkbox.Control cursor="pointer" />
                                <Checkbox.Label fontSize="sm" cursor="pointer">Selecionar todas as exibidas</Checkbox.Label>
                            </Checkbox.Root>
                            <Text fontSize="sm" fontWeight="semibold" role="status">
                                {selectedIds.length === 0 ? "Nenhuma selecionada" : selectedIds.length === 1 ? "1 selecionada" : `${selectedIds.length} selecionadas`}
                            </Text>
                        </Flex>
                        {selectedIds.length > MAX_BULK && (
                            <Text fontSize="sm" color="fg.error">São mais de {MAX_BULK} de uma vez. Use os filtros para escolher menos.</Text>
                        )}
                        {selectedIds.length > 0 && (
                            <Flex gap={2} wrap="wrap">
                                <Button size="sm" variant="outline" onClick={() => setSelected(new Set())}>Limpar seleção</Button>
                                <Button size="sm" disabled={selectedIds.length > MAX_BULK} onClick={() => setBulkEditing(true)}><LuPencil /> Editar selecionadas</Button>
                                <Button size="sm" colorPalette="red" variant="outline" disabled={selectedIds.length > MAX_BULK} onClick={() => setBulkDeleting(true)}><LuTrash2 /> Excluir selecionadas</Button>
                            </Flex>
                        )}
                    </Flex>
                )}

                {loading && <SpinnerLoading/>}

                {!loading && visible.length > 0 && (
                    <Table.ScrollArea w="full" overflowX="hidden" borderWidth={0}>
                        <Table.Root size="sm" w="full" display={{ base: "block", md: "table" }}>
                            <Table.Body display={{ base: "block", md: "table-row-group" }}>
                                {visible.map((transaction, index) => (
                                    <Fragment key={transaction.id}>
                                        {/* Phone only: the rows are grouped under their day, so the row itself does not show the date */}
                                        {transaction.transactioned_at.slice(0, 10) !== visible[index - 1]?.transactioned_at.slice(0, 10) && (
                                            <Table.Row data-day hideFrom="md" display="block">
                                                <Table.Cell display="block" pt={index === 0 ? 0 : 4} pb={1} px="10px" borderBottomWidth={0} color="fg.muted" fontSize="xs" fontWeight="semibold">
                                                    {formatDate(transaction.transactioned_at)}
                                                </Table.Cell>
                                            </Table.Row>
                                        )}
                                        {renderRow(transaction)}
                                    </Fragment>
                                ))}
                            </Table.Body>
                        </Table.Root>
                    </Table.ScrollArea>
                )}

                {/* Scrolling to here puts the next rows on the page; without the browser support for that, a button does */}
                {!loading && hasMore && (
                    <Box ref={end} w="full" textAlign="center" py={4}>
                        {canObserve ? <Box role="status" aria-label="Carregando mais transações"><SpinnerLoading /></Box> : (
                            <Button size="sm" variant="outline" onClick={() => setVisibleCount((count) => count + BATCH)}>
                                Mostrar mais
                            </Button>
                        )}
                    </Box>
                )}

                {!loading && filtered.length === 0 && (
                    <Text color="fg.muted">
                        {hasActiveFilters(filters) ? "Nenhuma transação encontrada com esses filtros." : "Nenhuma transação ainda."}
                    </Text>
                )}
            </Stack>

            {/* mounted only while open, so every opening starts on "Não alterar" */}
            {bulkEditing && (
            <BulkEditDialog
                ids={selectedIds}
                open={bulkEditing}
                onClose={() => setBulkEditing(false)}
                categories={sortedCategories}
                members={family.members}
                merchants={merchantsEnabled ? merchants : null}
                onDone={afterBulk}
            />
            )}
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
