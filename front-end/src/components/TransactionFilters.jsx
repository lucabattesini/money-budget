import { Button, Field, Flex, Input, NativeSelect } from "@chakra-ui/react";
import { EMPTY_FILTERS, hasActiveFilters } from "../lib/transactionFilters";
import { maskAmount } from "../lib/money";

// The filter bar above the table. `filters` is controlled by the page.
export default function TransactionFilters({ filters, onChange, categories }) {
    const set = (name) => (value) => onChange({ ...filters, [name]: value });

    return (
        <Flex direction="column" gap={3} w="280px" maxW="full">
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
                <Input size="sm" inputMode="numeric" placeholder="0,00" value={filters.min}
                    onChange={(e) => set("min")(maskAmount(e.target.value))} />
            </Field.Root>

            <Field.Root width="full">
                <Field.Label>Valor máximo</Field.Label>
                <Input size="sm" inputMode="numeric" placeholder="0,00" value={filters.max}
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
