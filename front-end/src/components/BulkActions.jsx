import { useState } from "react";
import { Button, Checkbox, CloseButton, Dialog, Field, Input, NativeSelect, Portal, Stack, Text } from "@chakra-ui/react";
import { bulkDeleteTransactions, bulkUpdateTransactions } from "../api/endpoints";
import { getToken } from "../lib/auth";
import customToaster from "../utils/customToaster";
import useBackClosesOverlay from "../lib/useBackClosesOverlay";
import CategoryPicker from "./CategoryPicker";

const MAX_MERCHANT = 100; // the size of the database column
const KEEP = ""; // every choice starts on "Não alterar"

const plural = (count) => (count === 1 ? "1 transação" : `${count} transações`);

function Select({ label, value, onChange, children }) {
    return (
        <Field.Root>
            <Field.Label>{label}</Field.Label>
            <NativeSelect.Root>
                <NativeSelect.Field value={value} onChange={(e) => onChange(e.target.value)}>
                    <option value={KEEP}>Não alterar</option>
                    {children}
                </NativeSelect.Field>
                <NativeSelect.Indicator />
            </NativeSelect.Root>
        </Field.Root>
    );
}

// Change the same things on many transactions. Whatever stays on "Não alterar" is left as each one has it.
// `merchants` is null while the family does not use merchants. Calls onDone() after the server accepted the change.
export function BulkEditDialog({ ids, open, onClose, categories, members, merchants, onDone }) {
    const [categoryId, setCategoryId] = useState(KEEP);
    const [personId, setPersonId] = useState(KEEP);
    const [excluded, setExcluded] = useState(KEEP); // "yes" | "no"
    const [merchant, setMerchant] = useState("");
    const [removeMerchant, setRemoveMerchant] = useState(false);
    const [saving, setSaving] = useState(false);
    useBackClosesOverlay(open, onClose);

    const changes = {
        ...(categoryId ? { category_id: categoryId } : {}),
        ...(personId ? { user_id: personId } : {}),
        ...(excluded ? { excluded: excluded === "yes" } : {}),
        ...(removeMerchant ? { merchant: "" } : merchant.trim() ? { merchant: merchant.trim() } : {}),
    };
    const nothingToChange = Object.keys(changes).length === 0;

    const save = async (event) => {
        event.preventDefault();
        setSaving(true);
        const result = await bulkUpdateTransactions(ids, changes, getToken());
        setSaving(false);
        if (result?.ok) {
            customToaster("Salvo", "success", `${plural(result.data.updated)} atualizada${result.data.updated === 1 ? "" : "s"}.`);
            onDone();
        } else {
            customToaster("Erro", "error", result?.detail && typeof result.detail === "string" ? result.detail : "Não foi possível atualizar as transações. Nada foi alterado.");
        }
    };

    return (
        <Dialog.Root open={open} onOpenChange={(e) => !e.open && onClose()} placement="center" lazyMount unmountOnExit>
            <Portal>
                <Dialog.Backdrop />
                <Dialog.Positioner>
                    <Dialog.Content as="form" onSubmit={save} noValidate>
                        <Dialog.Header><Dialog.Title>Editar {plural(ids.length)}</Dialog.Title></Dialog.Header>
                        <Dialog.Body>
                            <Stack gap={4}>
                                <Text fontSize="sm" color="fg.muted">O que você escolher vale para todas as selecionadas. O que ficar em "Não alterar" continua como está.</Text>
                                <Field.Root>
                                    <Field.Label>Categoria</Field.Label>
                                    <CategoryPicker categories={categories} value={categoryId} onChange={setCategoryId} emptyLabel="Não alterar" aria-label="Categoria" />
                                </Field.Root>
                                <Select label="Quem" value={personId} onChange={setPersonId}>
                                    {members.map((member) => <option key={member.id} value={member.id}>{member.name}</option>)}
                                </Select>
                                <Select label="Totais" value={excluded} onChange={setExcluded}>
                                    <option value="yes">Não contar nos totais</option>
                                    <option value="no">Contar nos totais</option>
                                </Select>
                                {merchants && (
                                    <Stack gap={2}>
                                        <Field.Root>
                                            <Field.Label>Estabelecimento</Field.Label>
                                            <Input
                                                list="bulk-merchant-options"
                                                maxLength={MAX_MERCHANT}
                                                value={merchant}
                                                disabled={removeMerchant}
                                                onChange={(e) => setMerchant(e.target.value)}
                                                placeholder="Não alterar (escolha ou digite um novo)"
                                            />
                                            <datalist id="bulk-merchant-options">
                                                {merchants.map((m) => <option key={m.id} value={m.name} />)}
                                            </datalist>
                                        </Field.Root>
                                        <Checkbox.Root checked={removeMerchant} onCheckedChange={(e) => setRemoveMerchant(Boolean(e.checked))}>
                                            <Checkbox.HiddenInput />
                                            <Checkbox.Control />
                                            <Checkbox.Label>Tirar o estabelecimento</Checkbox.Label>
                                        </Checkbox.Root>
                                    </Stack>
                                )}
                            </Stack>
                        </Dialog.Body>
                        <Dialog.Footer>
                            <Button variant="outline" onClick={onClose} disabled={saving}>Cancelar</Button>
                            <Button type="submit" loading={saving} disabled={nothingToChange}>Salvar</Button>
                        </Dialog.Footer>
                        <Dialog.CloseTrigger asChild><CloseButton size="sm" /></Dialog.CloseTrigger>
                    </Dialog.Content>
                </Dialog.Positioner>
            </Portal>
        </Dialog.Root>
    );
}

// Ask before deleting many transactions for good. Calls onDone() after they were deleted.
export function BulkDeleteDialog({ ids, open, onClose, onDone }) {
    const [deleting, setDeleting] = useState(false);
    useBackClosesOverlay(open, onClose);

    const remove = async () => {
        setDeleting(true);
        const result = await bulkDeleteTransactions(ids, getToken());
        setDeleting(false);
        if (result?.ok) {
            customToaster("Excluído", "success", `${plural(result.data.deleted)} excluída${result.data.deleted === 1 ? "" : "s"}.`);
            onDone();
        } else {
            customToaster("Erro", "error", "Não foi possível excluir as transações. Nada foi excluído.");
        }
    };

    return (
        <Dialog.Root open={open} onOpenChange={(e) => !e.open && onClose()} placement="center" role="alertdialog" lazyMount unmountOnExit>
            <Portal>
                <Dialog.Backdrop />
                <Dialog.Positioner>
                    <Dialog.Content>
                        <Dialog.Header><Dialog.Title>Excluir {plural(ids.length)}?</Dialog.Title></Dialog.Header>
                        <Dialog.Body><Text>Isso não pode ser desfeito.</Text></Dialog.Body>
                        <Dialog.Footer>
                            <Button variant="outline" onClick={onClose} disabled={deleting}>Cancelar</Button>
                            <Button colorPalette="red" onClick={remove} loading={deleting}>Excluir</Button>
                        </Dialog.Footer>
                    </Dialog.Content>
                </Dialog.Positioner>
            </Portal>
        </Dialog.Root>
    );
}
