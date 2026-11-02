import { useEffect, useState } from "react";
import { Button, Drawer, Field, Input, NativeSelect, Portal, Stack, Text, CloseButton } from "@chakra-ui/react";
import { insertNewTransaction } from "../api/endpoints";
import { getToken } from "../lib/auth";
import { digitsToCents, maskAmount } from "../lib/money";
import customToaster from "../utils/customToaster";

const MAX_LABEL = 25;

// Side panel with the form for a new transaction. Calls onSaved() after the API accepted it.
export default function AddTransactionDrawer({ open, onClose, categories, onSaved }) {
    const [amount, setAmount] = useState("");
    const [description, setDescription] = useState("");
    const [categoryId, setCategoryId] = useState("");
    const [errors, setErrors] = useState({});
    const [saving, setSaving] = useState(false);

    // Start empty every time the panel is opened
    useEffect(() => {
        if (open) {
            setAmount("");
            setDescription("");
            setCategoryId("");
            setErrors({});
        }
    }, [open]);

    const validate = () => {
        const found = {};
        if (digitsToCents(amount) <= 0) found.amount = "Informe um valor maior que zero";
        if (!description.trim()) found.description = "Informe uma descrição";
        if (!categoryId) found.category = "Escolha uma categoria";
        setErrors(found);
        return Object.keys(found).length === 0;
    };

    const handleSubmit = async (event) => {
        event.preventDefault();
        if (!validate()) return;

        setSaving(true);
        const result = await insertNewTransaction(
            { label: description.trim(), value: digitsToCents(amount), category_id: Number(categoryId) },
            getToken(),
        );
        setSaving(false);

        if (result && (result.status === 201 || result.status === 200)) {
            customToaster("Salvo", "success", "Sua transação foi salva!");
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
                            <Drawer.Title>Nova transação</Drawer.Title>
                        </Drawer.Header>
                        <Drawer.Body>
                            <Stack gap={5}>
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
