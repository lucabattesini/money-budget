import { useEffect, useState } from "react";
import { Button, Drawer, Field, Input, NativeSelect, Portal, RadioGroup, Stack, Text, CloseButton } from "@chakra-ui/react";
import { insertNewTransaction, updateTransaction } from "../api/endpoints";
import { getToken } from "../lib/auth";
import { digitsToCents, maskAmount } from "../lib/money";
import customToaster from "../utils/customToaster";

const MAX_LABEL = 25;

const two = (n) => String(n).padStart(2, "0");
const todayISO = () => {
    const now = new Date();
    return `${now.getFullYear()}-${two(now.getMonth() + 1)}-${two(now.getDate())}`;
};
const nowTime = () => {
    const now = new Date();
    return `${two(now.getHours())}:${two(now.getMinutes())}:${two(now.getSeconds())}`;
};

// Side panel with the form for a transaction: a new one, or `transaction` to edit it.
// Calls onSaved() after the API accepted it.
export default function TransactionDrawer({ open, onClose, categories, onSaved, transaction = null }) {
    const editing = transaction !== null;
    const [type, setType] = useState("debit");
    const [amount, setAmount] = useState("");
    const [date, setDate] = useState(todayISO());
    const [description, setDescription] = useState("");
    const [categoryId, setCategoryId] = useState("");
    const [errors, setErrors] = useState({});
    const [saving, setSaving] = useState(false);

    // Start from the transaction being edited (or empty) every time the panel is opened
    useEffect(() => {
        if (open) {
            setType(editing ? transaction.type ?? "debit" : "debit");
            setAmount(editing ? maskAmount(String(transaction.value)) : "");
            setDate(editing ? String(transaction.transactioned_at).slice(0, 10) : todayISO());
            setDescription(editing ? transaction.label ?? "" : "");
            const known = editing && categories.some((category) => category.id === transaction.category_id);
            setCategoryId(known ? String(transaction.category_id) : "");
            setErrors({});
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [open, transaction]);

    const validate = () => {
        const found = {};
        if (digitsToCents(amount) <= 0) found.amount = "Informe um valor maior que zero";
        if (!date) found.date = "Informe a data";
        else if (date > todayISO()) found.date = "A data não pode ser no futuro";
        if (!description.trim()) found.description = "Informe uma descrição";
        if (!categoryId) found.category = "Escolha uma categoria";
        setErrors(found);
        return Object.keys(found).length === 0;
    };

    const handleSubmit = async (event) => {
        event.preventDefault();
        if (!validate()) return;

        setSaving(true);
        // The form only picks a day; keep the time of day the transaction already had
        const time = editing ? String(transaction.transactioned_at).slice(11, 19) || nowTime() : nowTime();
        const payload = {
            label: description.trim(),
            value: digitsToCents(amount),
            category_id: Number(categoryId),
            type,
            transactioned_at: `${date}T${time}`,
        };
        const result = editing
            ? await updateTransaction(transaction.id, payload, getToken())
            : await insertNewTransaction(payload, getToken());
        setSaving(false);

        if (result && (result.status === 201 || result.status === 200)) {
            customToaster("Salvo", "success", editing ? "A transação foi atualizada!" : "Sua transação foi salva!");
            onSaved();
            onClose();
        } else {
            customToaster("Erro", "error", "Não foi possível salvar a transação. Tente novamente.");
        }
    };

    return (
        <Drawer.Root open={open} onOpenChange={(e) => !e.open && onClose()} placement="end" size="sm">
            <Portal>
                <Drawer.Backdrop />
                <Drawer.Positioner>
                    <Drawer.Content as="form" onSubmit={handleSubmit} noValidate>
                        <Drawer.Header>
                            <Drawer.Title>{editing ? "Editar transação" : "Nova transação"}</Drawer.Title>
                        </Drawer.Header>
                        <Drawer.Body>
                            <Stack gap={5}>
                                <Field.Root>
                                    <Field.Label>Tipo</Field.Label>
                                    <RadioGroup.Root value={type} onValueChange={(e) => setType(e.value)}>
                                        <Stack direction="row" gap={6}>
                                            {[["debit", "Débito"], ["credit", "Crédito"]].map(([value, label]) => (
                                                <RadioGroup.Item key={value} value={value}>
                                                    <RadioGroup.ItemHiddenInput />
                                                    <RadioGroup.ItemIndicator />
                                                    <RadioGroup.ItemText>{label}</RadioGroup.ItemText>
                                                </RadioGroup.Item>
                                            ))}
                                        </Stack>
                                    </RadioGroup.Root>
                                </Field.Root>

                                <Field.Root invalid={!!errors.amount}>
                                    <Field.Label>Valor</Field.Label>
                                    <Input
                                        inputMode="numeric"
                                        placeholder="0,00"
                                        value={amount}
                                        onChange={(e) => setAmount(maskAmount(e.target.value))}
                                    />
                                    <Text fontSize="xs" color="fg.muted">Em reais (R$)</Text>
                                    <Field.ErrorText>{errors.amount}</Field.ErrorText>
                                </Field.Root>

                                <Field.Root invalid={!!errors.date}>
                                    <Field.Label>Data</Field.Label>
                                    <Input type="date" value={date} max={todayISO()} onChange={(e) => setDate(e.target.value)} />
                                    <Field.ErrorText>{errors.date}</Field.ErrorText>
                                </Field.Root>

                                <Field.Root invalid={!!errors.description}>
                                    <Field.Label>Descrição</Field.Label>
                                    <Input
                                        maxLength={MAX_LABEL}
                                        value={description}
                                        onChange={(e) => setDescription(e.target.value)}
                                    />
                                    <Field.ErrorText>{errors.description}</Field.ErrorText>
                                </Field.Root>

                                <Field.Root invalid={!!errors.category}>
                                    <Field.Label>Categoria</Field.Label>
                                    <NativeSelect.Root>
                                        <NativeSelect.Field
                                            value={categoryId}
                                            onChange={(e) => setCategoryId(e.target.value)}
                                        >
                                            <option value="">Selecione</option>
                                            {categories.map((category) => (
                                                <option key={category.id} value={category.id}>{category.name}</option>
                                            ))}
                                        </NativeSelect.Field>
                                        <NativeSelect.Indicator />
                                    </NativeSelect.Root>
                                    <Field.ErrorText>{errors.category}</Field.ErrorText>
                                </Field.Root>
                            </Stack>
                        </Drawer.Body>
                        <Drawer.Footer>
                            <Button variant="outline" onClick={onClose} disabled={saving}>Cancelar</Button>
                            <Button type="submit" loading={saving}>Salvar</Button>
                        </Drawer.Footer>
                        <Drawer.CloseTrigger asChild>
                            <CloseButton size="sm" />
                        </Drawer.CloseTrigger>
                    </Drawer.Content>
                </Drawer.Positioner>
            </Portal>
        </Drawer.Root>
    );
}
