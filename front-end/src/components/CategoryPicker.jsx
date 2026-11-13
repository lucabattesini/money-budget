import { useMemo, useState } from "react";
import { flushSync } from "react-dom";
import { Combobox, Portal, createListCollection } from "@chakra-ui/react";
import { groupCategories, matchesSearch } from "../lib/categoryName";

const NO_EXTRA = []; // a fixed empty list: a new [] on every render would redo the grouping of every picker every time
const NONE = "__none__"; // the value of the "no category chosen" choice (an empty value cannot be selected)

/**
 * The one way to choose a category: a box that shows the chosen one, opens a list when clicked, and narrows it as the
 * person types (capitals, accents and the emoji of a name do not matter). Categories are listed under their group
 * headings, the groups in their own order and the categories A-Z, the same as the categories page.
 *
 * value / onChange work with the category id as a string ("" is none).
 * emptyLabel: adds a first choice that means "none" (the filters' "Todas"). extra: more first choices, [{ value, label }]
 * (the import's "Criar uma categoria nova"). variant "inline" looks like the text of a row: for changing in place.
 */
export default function CategoryPicker({
    categories, value, onChange, emptyLabel, extra = NO_EXTRA, placeholder = "Escolha uma categoria", label, id,
    invalid = false, disabled = false, variant = "field", size = "md", defaultOpen = false, onClosed, ...inputProps
}) {
    const [typed, setTyped] = useState("");

    const items = useMemo(() => {
        const found = typed.trim() === "" ? categories : categories.filter((category) => matchesSearch(category, typed));
        const groups = groupCategories(found).map((group) => ({
            ...group,
            items: group.categories.map((category) => ({ value: String(category.id), label: category.name })),
        }));
        const first = [
            ...(emptyLabel ? [{ value: NONE, label: emptyLabel }] : []),
            ...extra.map((choice) => ({ value: String(choice.value), label: choice.label })),
        ].filter((choice) => typed.trim() === "" || matchesSearch({ name: choice.label }, typed));
        return { groups, first };
    }, [categories, typed, emptyLabel, extra]);

    const collection = useMemo(
        () => createListCollection({ items: [...items.first, ...items.groups.flatMap((group) => group.items)], itemToString: (item) => item.label, itemToValue: (item) => item.value }),
        [items],
    );

    const chosen = value === "" || value == null ? (emptyLabel ? NONE : null) : String(value);
    const nothing = items.first.length === 0 && items.groups.length === 0;
    const inline = variant === "inline";

    return (
        <Combobox.Root
            collection={collection}
            value={chosen ? [chosen] : []}
            onValueChange={({ value: next }) => onChange(next[0] === undefined || next[0] === NONE ? "" : next[0])}
            // What is typed only narrows the list; the text itself belongs to the box (writing it from here lost keys typed fast).
            // Once a choice is made, the next opening shows every category again.
            onInputValueChange={({ inputValue, reason }) => flushSync(() => setTyped(reason === "input-change" ? inputValue : ""))}
            openOnClick
            defaultOpen={defaultOpen}
            onOpenChange={({ open }) => { if (!open && onClosed) onClosed(); }}
            lazyMount
            unmountOnExit
            invalid={invalid}
            disabled={disabled}
            size={size}
            ids={id ? { input: id } : undefined}
            width={inline ? "full" : undefined}
            positioning={{ sameWidth: !inline }}
        >
            {label && <Combobox.Label>{label}</Combobox.Label>}
            <Combobox.Control>
                <Combobox.Input
                    placeholder={placeholder}
                    onClick={(event) => {
                        // The chosen name is selected, so typing starts a new search. After the box has written its own text (the same
                        // text, but that moves the caret), so the selection is made a moment later.
                        const input = event.currentTarget;
                        setTimeout(() => input.setSelectionRange(0, input.value.length), 0);
                    }}
                    {...(inline ? { variant: "subtle", bg: "transparent", borderWidth: 0, px: 2, h: "auto", minH: "28px", fontSize: "sm", color: "fg.muted", textOverflow: "ellipsis", cursor: "pointer", rounded: "md", _hover: { bg: "bg.muted" }, _focus: { cursor: "text" } } : {})}
                    {...inputProps}
                />
                {!inline && (
                    <Combobox.IndicatorGroup>
                        <Combobox.Trigger />
                    </Combobox.IndicatorGroup>
                )}
            </Combobox.Control>
            <Portal>
                <Combobox.Positioner>
                    <Combobox.Content minW={inline ? "16rem" : undefined} maxH="min(20rem, 60dvh)">
                        {nothing && <Combobox.Empty>Nenhuma categoria encontrada</Combobox.Empty>}
                        {items.first.map((choice) => (
                            <Combobox.Item key={choice.value} item={choice}>
                                {choice.label}
                                <Combobox.ItemIndicator />
                            </Combobox.Item>
                        ))}
                        {items.groups.map((group) => (
                            <Combobox.ItemGroup key={group.id}>
                                {group.name && <Combobox.ItemGroupLabel>{group.name}</Combobox.ItemGroupLabel>}
                                {group.items.map((item) => (
                                    <Combobox.Item key={item.value} item={item}>
                                        {item.label}
                                        <Combobox.ItemIndicator />
                                    </Combobox.Item>
                                ))}
                            </Combobox.ItemGroup>
                        ))}
                    </Combobox.Content>
                </Combobox.Positioner>
            </Portal>
        </Combobox.Root>
    );
}
