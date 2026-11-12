import { useEffect, useState } from "react";
import { Button, Checkbox, Drawer, Field, Input, NativeSelect, Portal, RadioGroup, Stack, Text, CloseButton } from "@chakra-ui/react";
import { insertNewTransaction, updateTransaction } from "../api/endpoints";
import { getToken } from "../lib/auth";
import { digitsToCents, maskAmount } from "../lib/money";
import AmountInput from "./AmountInput";
import { CURRENCIES, familyNow, useLocale } from "../lib/locale";
import { leftOutByDefault } from "../lib/totals";
import customToaster from "../utils/customToaster";
import useBackClosesOverlay from "../lib/useBackClosesOverlay";

const MAX_LABEL = 25;
const MAX_MERCHANT = 100; // the size of the database column

// A label with a red asterisk. The asterisk is drawn by CSS, so the label text stays just the name.
function RequiredLabel({ children }) {
    return (
        <Field.Label _after={{ content: '" *"', color: "red.500", fontWeight: "bold" }}>{children}</Field.Label>
    );
}

const two = (n) => String(n).padStart(2, "0");
const todayISO = () => {
    const now = familyNow();
    return `${now.getFullYear()}-${two(now.getMonth() + 1)}-${two(now.getDate())}`;
};
const nowTime = () => {
    const now = familyNow();
    return `${two(now.getHours())}:${two(now.getMinutes())}:${two(now.getSeconds())}`;
};

// Side panel with the form for a transaction: a new one, or `transaction` to edit it.
// Calls onSaved() after the API accepted it.
export default function TransactionDrawer({ open, onClose, categories, members = [], me = null, merchants = null, onSaved, transaction = null }) {
    const { currency } = useLocale(); // the amount is typed in the family's currency
    const unit = CURRENCIES.find((c) => c.code === currency);
    const editing = transaction !== null;
    const [type, setType] = useState("debit");
    const [amount, setAmount] = useState("");
    const [date, setDate] = useState(todayISO());
    const [description, setDescription] = useState("");
    const [categoryId, setCategoryId] = useState("");
    const [personId, setPersonId] = useState(""); // who it belongs to
    const [merchant, setMerchant] = useState(""); // the name typed or picked; only while the family has merchants (a list)
    const [excluded, setExcluded] = useState(false); // left out of the totals
    const [excludedTouched, setExcludedTouched] = useState(false); // once the person decides, the category stops deciding
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
            // A new one belongs to the logged-in person; an edited one to its person (empty if they left the family)
            const person = editing ? transaction.user_id : me;
            setPersonId(members.some((member) => member.id === person) ? String(person) : "");
            setMerchant(editing ? merchants?.find((m) => m.id === transaction.merchant_id)?.name ?? "" : "");
            setExcluded(editing ? Boolean(transaction.excluded) : false);
            setExcludedTouched(editing);
            setErrors({});
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [open, transaction]);

    useBackClosesOverlay(open, onClose);

    // Choosing a category sets the checkbox (a transfer or a card payment starts out left out) until the person decides
    const chooseCategory = (id) => {
        setCategoryId(id);
        if (!excludedTouched) setExcluded(leftOutByDefault(categories.find((category) => String(category.id) === id)));
    };

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
            category_id: categoryId,
            type,
            transactioned_at: `${date}T${time}`,
            // Left out when unknown: the server then keeps the person (edit) or uses the logged-in one (new)
            ...(personId ? { user_id: personId } : {}),
            // "" takes the merchant off an edited transaction; a new one without it simply has none
            ...(merchants ? { merchant: merchant.trim() } : {}),
            excluded,
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
        <Drawer.Root open={open} onOpenChange={(e) => !e.open && onClose()} placement="end" size={{ base: "full", md: "sm" }}>
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
                                                <RadioGroup.Item key={value} value={value} minH={{ base: "44px", md: "auto" }} pr={2}>
                                                    <RadioGroup.ItemHiddenInput />
                                                    <RadioGroup.ItemIndicator />
                                                    <RadioGroup.ItemText>{label}</RadioGroup.ItemText>
                                                </RadioGroup.Item>
                                            ))}
                                        </Stack>
                                    </RadioGroup.Root>
                                </Field.Root>

                                <Field.Root required invalid={!!errors.amount}>
                                    <RequiredLabel>Valor</RequiredLabel>
                                    <AmountInput
                                        label="Valor"
                                        placeholder={maskAmount("0")}
                                        value={amount}
                                        onChange={(e) => setAmount(maskAmount(e.target.value))}
                                    />
                                    <Text fontSize="xs" color="fg.muted">Em {unit.name} ({unit.symbol})</Text>
                                    <Field.ErrorText>{errors.amount}</Field.ErrorText>
                                </Field.Root>

                                <Field.Root required invalid={!!errors.date}>
                                    <RequiredLabel>Data</RequiredLabel>
                                    <Input type="date" value={date} max={todayISO()} onChange={(e) => setDate(e.target.value)} />
                                    <Field.ErrorText>{errors.date}</Field.ErrorText>
                                </Field.Root>

                                <Field.Root required invalid={!!errors.description}>
                                    <RequiredLabel>Descrição</RequiredLabel>
                                    <Input
                                        maxLength={MAX_LABEL}
                                        value={description}
                                        onChange={(e) => setDescription(e.target.value)}
                                    />
                                    <Field.ErrorText>{errors.description}</Field.ErrorText>
                                </Field.Root>

                                <Field.Root required invalid={!!errors.category}>
                                    <RequiredLabel>Categoria</RequiredLabel>
                                    <NativeSelect.Root>
                                        <NativeSelect.Field
                                            value={categoryId}
                                            onChange={(e) => chooseCategory(e.target.value)}
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

                                {merchants && (
                                    <Field.Root>
                                        <Field.Label>Estabelecimento</Field.Label>
                                        <Input
                                            list="merchant-options"
                                            maxLength={MAX_MERCHANT}
                                            value={merchant}
                                            onChange={(e) => setMerchant(e.target.value)}
                                            placeholder="Escolha ou digite um novo"
                                        />
                                        <datalist id="merchant-options">
                                            {merchants.map((m) => (
                                                <option key={m.id} value={m.name} />
                                            ))}
                                        </datalist>
                                    </Field.Root>
                                )}

                                <Field.Root>
                                    <Field.Label>Quem</Field.Label>
                                    <NativeSelect.Root>
                                        <NativeSelect.Field value={personId} onChange={(e) => setPersonId(e.target.value)}>
                                            {personId === "" && <option value="">Selecione</option>}
                                            {members.map((member) => (
                                                <option key={member.id} value={member.id}>{member.name}</option>
                                            ))}
                                        </NativeSelect.Field>
                                        <NativeSelect.Indicator />
                                    </NativeSelect.Root>
                                </Field.Root>

                                <Field.Root>
                                    <Checkbox.Root
                                        checked={excluded}
                                        onCheckedChange={(e) => {
                                            setExcluded(Boolean(e.checked));
                                            setExcludedTouched(true);
                                        }}
                                    >
                                        <Checkbox.HiddenInput />
                                        <Checkbox.Control />
                                        <Checkbox.Label>Não contar nos totais</Checkbox.Label>
                                    </Checkbox.Root>
                                    <Field.HelperText>
                                        A transação continua na lista, mas fica de fora do painel, do orçamento e das respostas do assistente.
                                    </Field.HelperText>
                                </Field.Root>
                            </Stack>
                        </Drawer.Body>
                        <Drawer.Footer>
                            <Button variant="outline" minH={{ base: "44px", md: "auto" }} onClick={onClose} disabled={saving}>Cancelar</Button>
                            <Button type="submit" minH={{ base: "44px", md: "auto" }} loading={saving}>Salvar</Button>
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
