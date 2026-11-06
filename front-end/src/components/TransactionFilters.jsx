import { Button, Field, Flex, Input, NativeSelect } from "@chakra-ui/react";
import { EMPTY_FILTERS, hasActiveFilters } from "../lib/transactionFilters";
import { maskAmount } from "../lib/money";
import { useLocale } from "../lib/locale";
import AmountInput from "./AmountInput";

// The filter bar above the table. `filters` is controlled by the page.
export default function TransactionFilters({ filters, onChange, categories, members = [], merchants = [] }) {
    useLocale(); // the amount fields are written in the family's language
    const set = (name) => (value) => onChange({ ...filters, [name]: value });

    return (
        <Flex direction="column" gap={3} w={{ base: "full", md: "280px" }}>
            <Field.Root width="full">
                <Field.Label>Buscar</Field.Label>
                <Input
                    size="sm"
                    placeholder="Descrição"
                    value={filters.search}
                    onChange={(e) => set("search")(e.target.value)}
                />
            </Field.Root>

            <Field.Root width="full">
                <Field.Label>Categoria</Field.Label>
                <NativeSelect.Root size="sm">
                    <NativeSelect.Field value={filters.category} onChange={(e) => set("category")(e.target.value)}>
                        <option value="">Todas</option>
                        {categories.map((category) => (
                            <option key={category.id} value={category.id}>{category.name}</option>
                        ))}
                    </NativeSelect.Field>
                    <NativeSelect.Indicator />
                </NativeSelect.Root>
            </Field.Root>

            {merchants.length > 0 && (
                <Field.Root width="full">
                    <Field.Label>Estabelecimento</Field.Label>
                    <NativeSelect.Root size="sm">
                        <NativeSelect.Field value={filters.merchant} onChange={(e) => set("merchant")(e.target.value)}>
                            <option value="">Todos</option>
                            {merchants.map((merchant) => (
                                <option key={merchant.id} value={merchant.id}>{merchant.name}</option>
                            ))}
                        </NativeSelect.Field>
                        <NativeSelect.Indicator />
                    </NativeSelect.Root>
                </Field.Root>
            )}

            {members.length > 0 && (
                <Field.Root width="full">
                    <Field.Label>Quem</Field.Label>
                    <NativeSelect.Root size="sm">
                        <NativeSelect.Field value={filters.person} onChange={(e) => set("person")(e.target.value)}>
                            <option value="">Todas</option>
                            {members.map((member) => (
                                <option key={member.id} value={member.id}>{member.name}</option>
                            ))}
                        </NativeSelect.Field>
                        <NativeSelect.Indicator />
                    </NativeSelect.Root>
                </Field.Root>
            )}

            <Field.Root width="full">
                <Field.Label>Tipo</Field.Label>
                <NativeSelect.Root size="sm">
                    <NativeSelect.Field value={filters.type} onChange={(e) => set("type")(e.target.value)}>
                        <option value="">Todos</option>
                        <option value="debit">Débito</option>
                        <option value="credit">Crédito</option>
                    </NativeSelect.Field>
                    <NativeSelect.Indicator />
                </NativeSelect.Root>
            </Field.Root>

            <Field.Root width="full">
                <Field.Label>Totais</Field.Label>
                <NativeSelect.Root size="sm">
                    <NativeSelect.Field value={filters.counting} onChange={(e) => set("counting")(e.target.value)}>
                        <option value="">Todas</option>
                        <option value="counted">Só as que contam</option>
                        <option value="left_out">Só as fora dos totais</option>
                    </NativeSelect.Field>
                    <NativeSelect.Indicator />
                </NativeSelect.Root>
            </Field.Root>

            <Field.Root width="full">
                <Field.Label>De</Field.Label>
                <Input size="sm" type="date" value={filters.from} max={filters.to || undefined}
                    onChange={(e) => set("from")(e.target.value)} />
            </Field.Root>

            <Field.Root width="full">
                <Field.Label>Até</Field.Label>
                <Input size="sm" type="date" value={filters.to} min={filters.from || undefined}
                    onChange={(e) => set("to")(e.target.value)} />
            </Field.Root>

            <Field.Root width="full">
                <Field.Label>Valor mínimo</Field.Label>
                <AmountInput size="sm" label="Valor mínimo" placeholder={maskAmount("0")} value={filters.min}
                    onChange={(e) => set("min")(maskAmount(e.target.value))} />
            </Field.Root>

            <Field.Root width="full">
                <Field.Label>Valor máximo</Field.Label>
                <AmountInput size="sm" label="Valor máximo" placeholder={maskAmount("0")} value={filters.max}
                    onChange={(e) => set("max")(maskAmount(e.target.value))} />
            </Field.Root>

            {hasActiveFilters(filters) && (
                <Button size="sm" variant="ghost" onClick={() => onChange(EMPTY_FILTERS)}>
                    Limpar filtros
                </Button>
            )}
        </Flex>
    );
}
