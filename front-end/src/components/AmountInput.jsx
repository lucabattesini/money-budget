import { Input, InputGroup, Text } from "@chakra-ui/react";
import { CURRENCIES, useLocale } from "../lib/locale";

// A box to type an amount in: the family's currency symbol sits in front of the number, outside the typed text, so
// the cursor and deleting work as in any other field. `label` is the field's name; the screen reader reads it with the
// currency ("Valor em dólares (US$)"). The caller keeps the value and masks it (see maskAmount in lib/money.js).
export default function AmountInput({ label, ...props }) {
    const { currency } = useLocale();
    const unit = CURRENCIES.find((c) => c.code === currency);
    return (
        <InputGroup
            startElement={<Text as="span" fontSize="sm" color="fg.muted">{unit.symbol}</Text>}
            startElementProps={{ px: 3 }}
        >
            <Input
                inputMode="numeric"
                aria-label={`${label} em ${unit.name} (${unit.symbol})`}
                ps={`calc(${unit.symbol.length}ch + 1.5rem)`}
                {...props}
            />
        </InputGroup>
    );
}
