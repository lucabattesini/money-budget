import { useState } from "react";
import { useLocation, useSearchParams } from "react-router-dom";
import { Box, Button, Checkbox, Dialog, Field, Flex, Heading, Input, Portal, RadioGroup, Stack, Table, Text } from "@chakra-ui/react";
import { bulkDeleteTransactions, getDuplicateTransactions } from "../api/endpoints";
import { getToken } from "../lib/auth";
import { formatCents } from "../lib/money";
import { familyNow, formatDate } from "../lib/locale";
import customToaster from "../utils/customToaster";
import PageHeading from "../components/PageHeading";
import useBackClosesOverlay from "../lib/useBackClosesOverlay";

const MAX_DELETE_AT_ONCE = 500; // what the server accepts in one request
const DELETE_ALL = "none"; // the person wants none of the group kept
const KEEP_ALL = "all"; // the choice of a group the person wants to leave alone
const two = (n) => String(n).padStart(2, "0");
const iso = (d) => `${d.getFullYear()}-${two(d.getMonth() + 1)}-${two(d.getDate())}`;

const count = (n, one, many) => (n === 1 ? `1 ${one}` : `${n} ${many}`);

const groupKey = (group) => group.map((transaction) => transaction.id).join();

// Find transactions that look entered twice in a period, choose which one to keep in each group, and delete the others.
export default function AccountDuplicates() {
    const today = familyNow();
    // The period lives in the address (?from=&to=): reload keeps them, and not one entry per keystroke
    const { state: routeState } = useLocation();
    const [params, setParams] = useSearchParams();
    const isDay = (value) => /^\d{4}-\d{2}-\d{2}$/.test(value ?? "") && iso(new Date(`${value}T00:00:00`)) === value; // a real calendar day
    const day = (name, fallback) => (isDay(params.get(name)) ? params.get(name) : fallback);
    const start = params.get("from") === "" ? "" : day("from", iso(new Date(today.getFullYear(), today.getMonth() - 3, today.getDate()))); // three months back
    const end = params.get("to") === "" ? "" : day("to", iso(today));
    const [ignoreExcluded, setIgnoreExcluded] = useState(false); // leave out what does not count in the totals
    const change = (name, value) => setParams((current) => {
        const next = new URLSearchParams(current);
        next.set(name, value);
        return next;
    }, { replace: true, state: routeState });
    const setStart = (value) => change("from", value);
    const setEnd = (value) => change("to", value);
    const [searching, setSearching] = useState(false);
    const [groups, setGroups] = useState(null); // null: not searched yet
    const [keep, setKeep] = useState({}); // group key -> id of the one kept, or KEEP_ALL, or DELETE_ALL
    const [pending, setPending] = useState(null); // ids waiting for the final confirmation, or null
    const [deleting, setDeleting] = useState(false);

    const rangeError = !start || !end ? "Informe as duas datas" : start > end ? "A data inicial não pode ser depois da final" : null;

    const search = async () => {
        if (rangeError) return;
        setSearching(true);
        const result = await getDuplicateTransactions(start, end, getToken(), ignoreExcluded);
        setSearching(false);
        if (!result?.ok) {
            customToaster("Erro", "error", "Não foi possível procurar duplicatas. Tente novamente.");
            return;
        }
        setGroups(result.data);
        // The first one saved is kept unless the person says otherwise
        // Choices already made survive a refresh for the groups that are still the same
        setKeep((current) => Object.fromEntries(result.data.map((group) => {
            const before = current[groupKey(group)];
            return [groupKey(group), before ?? group[0].id];
        })));
    };

    const idsToDelete = (group) =>
        keep[groupKey(group)] === KEEP_ALL ? [] : group.filter((transaction) => transaction.id !== keep[groupKey(group)]).map((transaction) => transaction.id);
    const toDelete = (groups ?? []).flatMap(idsToDelete);
    const groupsToClean = (groups ?? []).filter((group) => keep[groupKey(group)] !== KEEP_ALL).length;
    const wholeList = pending !== null && pending.length === toDelete.length && pending.every((id) => toDelete.includes(id));

    const tooMany = toDelete.length > MAX_DELETE_AT_ONCE;

    const remove = async () => {
        setDeleting(true);
        const result = await bulkDeleteTransactions(pending, getToken());
        setDeleting(false);
        setPending(null);
        if (!result?.ok) {
            customToaster("Erro", "error", "Não foi possível excluir as transações. Nada foi excluído.");
            return;
        }
        customToaster("Excluído", "success", `${count(result.data.deleted, "transação excluída", "transações excluídas")}.`);
        search();
    };

    useBackClosesOverlay(pending !== null, () => setPending(null));

    return (
        <Stack gap={6} maxW="3xl">
            <PageHeading title="Duplicatas">
                Transações do mesmo dia, com o mesmo valor e o mesmo tipo aparecem juntas. Em cada grupo, escolha qual manter; as outras são excluídas.
            </PageHeading>

            <Flex gap={4} wrap="wrap" align="end">
                <Field.Root w="auto" invalid={Boolean(rangeError)}>
                    <Field.Label>De</Field.Label>
                    <Input type="date" value={start} max={end || undefined} onChange={(e) => setStart(e.target.value)} />
                </Field.Root>
                <Field.Root w="auto" invalid={Boolean(rangeError)}>
                    <Field.Label>Até</Field.Label>
                    <Input type="date" value={end} min={start || undefined} onChange={(e) => setEnd(e.target.value)} />
                </Field.Root>
                <Checkbox.Root cursor="pointer" checked={ignoreExcluded} onCheckedChange={(e) => setIgnoreExcluded(Boolean(e.checked))} alignSelf="center">
                    <Checkbox.HiddenInput />
                    <Checkbox.Control cursor="pointer" />
                    <Checkbox.Label cursor="pointer">Ignorar as que não contam nos totais</Checkbox.Label>
                </Checkbox.Root>
                <Button onClick={search} loading={searching} disabled={Boolean(rangeError)}>Procurar</Button>
            </Flex>
            {rangeError && <Text color="fg.error" fontSize="sm">{rangeError}</Text>}

            {groups !== null && groups.length === 0 && (
                <Text role="status" color="fg.muted">Nenhuma duplicata encontrada nesse período.</Text>
            )}

            {groups !== null && groups.length > 0 && (
                <Stack gap={4}>
                    <Text role="status" fontWeight="semibold">{count(groups.length, "grupo encontrado", "grupos encontrados")}</Text>
                    {groups.map((group, index) => (
                        <Box key={groupKey(group)} borderWidth="1px" borderRadius="md" p={3}>
                            <Text fontWeight="semibold" mb={2}>
                                {formatDate(group[0].transactioned_at)} · {group[0].type === "credit" ? "+" : "-"} {formatCents(group[0].value)}
                            </Text>
                            <RadioGroup.Root value={keep[groupKey(group)]} onValueChange={(e) => setKeep((current) => ({ ...current, [groupKey(group)]: e.value }))}>
                                {/* One row per transaction with the same columns in every group, so the copies can be compared side by side */}
                                <Table.Root size="sm" tableLayout="fixed" w="full">
                                    <Table.Header>
                                        <Table.Row>
                                            <Table.ColumnHeader w="90px">Manter</Table.ColumnHeader>
                                            <Table.ColumnHeader>Descrição</Table.ColumnHeader>
                                            <Table.ColumnHeader hideBelow="md">Categoria</Table.ColumnHeader>
                                            <Table.ColumnHeader hideBelow="md" w="140px">Quem</Table.ColumnHeader>
                                            <Table.ColumnHeader hideBelow="md" w="120px">Salva em</Table.ColumnHeader>
                                        </Table.Row>
                                    </Table.Header>
                                    <Table.Body>
                                        {group.map((transaction) => {
                                            const deleted = keep[groupKey(group)] !== KEEP_ALL && keep[groupKey(group)] !== transaction.id; // marked to go when the group is cleaned
                                            return (
                                                <Table.Row key={transaction.id} opacity={deleted ? 0.5 : 1} bg={deleted ? "bg.muted" : undefined}>
                                                    <Table.Cell>
                                                        <RadioGroup.Item cursor="pointer" value={transaction.id}>
                                                            <RadioGroup.ItemHiddenInput aria-label={`Manter ${transaction.label}`} />
                                                            <RadioGroup.ItemIndicator />
                                                            <RadioGroup.ItemText fontSize="xs" color={deleted ? "fg.error" : "fg.muted"}>{deleted ? "excluir" : "manter"}</RadioGroup.ItemText>
                                                        </RadioGroup.Item>
                                                    </Table.Cell>
                                                    <Table.Cell wordBreak="break-word" textDecoration={deleted ? "line-through" : undefined}>
                                                        {transaction.label}
                                                        {transaction.excluded && <Text as="span" color="fg.muted" fontSize="xs"> · fora dos totais</Text>}
                                                    </Table.Cell>
                                                    <Table.Cell hideBelow="md" color="fg.muted">{transaction.category_name ?? "Sem categoria"}</Table.Cell>
                                                    <Table.Cell hideBelow="md" color="fg.muted">{transaction.user_name ?? ""}</Table.Cell>
                                                    <Table.Cell hideBelow="md" color="fg.muted">{transaction.created_at ? formatDate(transaction.created_at) : ""}</Table.Cell>
                                                </Table.Row>
                                            );
                                        })}
                                    </Table.Body>
                                </Table.Root>
                                <Flex gap={6} wrap="wrap" mt={2} align="center">
                                <RadioGroup.Item cursor="pointer" value={DELETE_ALL}>
                                    <RadioGroup.ItemHiddenInput />
                                    <RadioGroup.ItemIndicator />
                                    <RadioGroup.ItemText color="fg.error">Excluir todas</RadioGroup.ItemText>
                                </RadioGroup.Item>
                                <RadioGroup.Item cursor="pointer" value={KEEP_ALL}>
                                    <RadioGroup.ItemHiddenInput />
                                    <RadioGroup.ItemIndicator />
                                    <RadioGroup.ItemText color="fg.muted">Manter todas (não são duplicatas)</RadioGroup.ItemText>
                                </RadioGroup.Item>
                            {/* Does what was chosen for this group only */}
                            <Button ml="auto" size="sm" variant="outline" colorPalette="red" disabled={idsToDelete(group).length === 0}
                                aria-label={`Aplicar escolha do grupo ${index + 1}`} onClick={() => setPending(idsToDelete(group))}>
                                Aplicar neste grupo
                            </Button>
                                </Flex>
                            </RadioGroup.Root>
                        </Box>
                    ))}

                    <Button alignSelf="start" colorPalette="red" disabled={toDelete.length === 0 || tooMany} onClick={() => setPending(toDelete)}>
                        Excluir {count(toDelete.length, "duplicada", "duplicadas")}
                    </Button>
                    {tooMany && (
                        <Text color="fg.error" fontSize="sm">
                            São mais de {MAX_DELETE_AT_ONCE} de uma vez. Escolha um período menor ou marque "manter todas" em alguns grupos.
                        </Text>
                    )}
                </Stack>
            )}

            <Dialog.Root open={pending !== null} onOpenChange={(e) => !e.open && setPending(null)} placement="center" role="alertdialog" lazyMount unmountOnExit>
                <Portal>
                    <Dialog.Backdrop />
                    <Dialog.Positioner>
                        <Dialog.Content>
                            <Dialog.Header><Dialog.Title>Excluir {count(pending?.length ?? 0, "transação", "transações")}?</Dialog.Title></Dialog.Header>
                            <Dialog.Body>
                                <Text>
                                    {wholeList
                                        ? `Em ${count(groupsToClean, "grupo", "grupos")}, a escolhida fica e as outras são excluídas. Isso não pode ser desfeito.`
                                        : "Isso não pode ser desfeito."}
                                </Text>
                            </Dialog.Body>
                            <Dialog.Footer>
                                <Button variant="outline" onClick={() => setPending(null)} disabled={deleting}>Cancelar</Button>
                                <Button colorPalette="red" onClick={remove} loading={deleting}>Excluir</Button>
                            </Dialog.Footer>
                        </Dialog.Content>
                    </Dialog.Positioner>
                </Portal>
            </Dialog.Root>
        </Stack>
    );
}
