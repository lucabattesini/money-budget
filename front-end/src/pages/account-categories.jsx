import { useCallback, useEffect, useRef, useState } from "react";
import { Badge, Box, Button, CloseButton, Drawer, Field, HStack, Heading, Input, NativeSelect, Portal, Spinner, Stack, Text, Wrap } from "@chakra-ui/react";
import { LuPencil, LuPlus, LuTrash2 } from "react-icons/lu";
import { createCategory, deleteCategory, getAllCategories, getCategoryGroups, updateCategory } from "../api/endpoints";
import { getToken } from "../lib/auth";
import { EMOJI_CHOICES, compareCategories, joinName, splitName } from "../lib/categoryName";
import customToaster from "../utils/customToaster";
import PageHeading from "../components/PageHeading";
import useBackClosesOverlay from "../lib/useBackClosesOverlay";

const MAX_NAME = 100; // characters of the whole name, emoji included: the size of the database column
const length = (text) => Array.from(text).length; // by characters, like the server (an emoji can be two UTF-16 units)
const FALLBACK_GROUP = "Outros";

// A label with a red asterisk, like the transaction form.
function RequiredLabel({ children }) {
    return <Field.Label _after={{ content: '" *"', color: "red.500", fontWeight: "bold" }}>{children}</Field.Label>;
}

// The emojis to choose from (one, or none), as a real radio group: one tab stop (the selected one), the arrow keys
// move and select, Home and End jump to the ends. An emoji the category already has stays selectable even if it is
// not in the list.
function EmojiGrid({ value, onChange }) {
    const choices = value && !EMOJI_CHOICES.includes(value) ? [value, ...EMOJI_CHOICES] : EMOJI_CHOICES;
    const options = ["", ...choices]; // "" is "Sem emoji"
    const buttons = useRef([]);
    const selected = Math.max(0, options.indexOf(value));

    const move = (to) => {
        const next = (to + options.length) % options.length;
        onChange(options[next]);
        buttons.current[next]?.focus();
    };
    const handleKeyDown = (event, index) => {
        const keys = { ArrowRight: index + 1, ArrowDown: index + 1, ArrowLeft: index - 1, ArrowUp: index - 1, Home: 0, End: options.length - 1 };
        if (event.key in keys) {
            event.preventDefault();
            move(keys[event.key]);
        }
    };

    return (
        <Wrap role="radiogroup" aria-label="Emoji" gap={1}>
            {options.map((emoji, index) => (
                <Button
                    key={emoji || "none"}
                    ref={(element) => (buttons.current[index] = element)}
                    size={emoji ? "sm" : "xs"}
                    variant={value === emoji ? "solid" : emoji ? "ghost" : "outline"}
                    role="radio"
                    aria-checked={value === emoji}
                    aria-label={emoji || undefined}
                    tabIndex={index === selected ? 0 : -1}
                    onClick={() => onChange(emoji)}
                    onKeyDown={(event) => handleKeyDown(event, index)}
                    fontSize={emoji ? "lg" : undefined}
                    px={emoji ? 1 : undefined}
                    minW={emoji ? "9" : undefined}
                >
                    {emoji || "Sem emoji"}
                </Button>
            ))}
        </Wrap>
    );
}

// Side panel to add a category, or to edit `category` (its name and group).
function CategoryDrawer({ open, onClose, groups, category, defaultGroupId, onSaved }) {
    useBackClosesOverlay(open, onClose);
    const editing = category !== null;
    const [emoji, setEmoji] = useState("");
    const [name, setName] = useState("");
    const [groupId, setGroupId] = useState("");
    const [error, setError] = useState("");
    const [saving, setSaving] = useState(false);

    // Start from the category being edited (or empty, in "Outros") every time the panel opens
    useEffect(() => {
        if (open) {
            // The emoji is the start of the stored name: show it in the grid, and the words in the text box
            const parts = editing ? splitName(category.name) : { emoji: "", text: "" };
            setEmoji(parts.emoji);
            setName(parts.text);
            // A new category starts in the group whose button was clicked ("Outros" if there is none)
            const fallback = groups.find((group) => group.name === FALLBACK_GROUP);
            setGroupId(String(editing ? category.group_id : defaultGroupId ?? fallback?.id ?? ""));
            setError("");
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [open, category, defaultGroupId]);

    const handleSubmit = async (event) => {
        event.preventDefault();
        // An emoji typed into the text box (from the keyboard's emoji panel) counts too
        const typed = splitName(name);
        const words = typed.text;
        if (!words) {
            setError("O nome da categoria não pode ficar vazio.");
            return;
        }
        const fullName = joinName(emoji || typed.emoji, words);
        if (length(fullName) > MAX_NAME) {
            // For example a long name, then a long emoji chosen afterwards
            setError(`O nome da categoria, com o emoji, pode ter no máximo ${MAX_NAME} caracteres.`);
            return;
        }
        setSaving(true);
        const payload = { name: fullName, group_id: groupId };
        const result = editing
            ? await updateCategory(category.id, payload, getToken())
            : await createCategory(payload, getToken());
        setSaving(false);

        if (result.ok) {
            customToaster("Salvo", "success", editing ? "A categoria foi atualizada!" : "A categoria foi criada!");
            onSaved();
            onClose();
        } else if (result.status === 409 || result.status === 422) {
            setError(result.detail); // the server says what is wrong, for example that the name already exists
        } else if (result.status === 404) {
            // The category is gone (deleted in another tab, say): say so and show the real list
            customToaster("Erro", "error", result.detail || "Essa categoria não existe mais.");
            onSaved();
            onClose();
        } else {
            customToaster("Erro", "error", "Não foi possível salvar a categoria. Tente novamente.");
        }
    };

    return (
        <Drawer.Root open={open} onOpenChange={(e) => !e.open && onClose()} placement="end" size="sm">
            <Portal>
                <Drawer.Backdrop />
                <Drawer.Positioner>
                    <Drawer.Content as="form" onSubmit={handleSubmit} noValidate>
                        <Drawer.Header>
                            <Drawer.Title>{editing ? "Editar categoria" : "Nova categoria"}</Drawer.Title>
                        </Drawer.Header>
                        <Drawer.Body>
                            <Stack gap={5}>
                                <Text fontSize="xs" color="fg.muted">
                                    <Text as="span" color="red.500" fontWeight="bold">*</Text> campo obrigatório
                                </Text>

                                <Field.Root required invalid={!!error}>
                                    <RequiredLabel>Nome</RequiredLabel>
                                    <Input
                                        value={name}
                                        onChange={(e) => {
                                            // Cut to what still fits once the emoji and its space are put in front
                                            const room = MAX_NAME - (emoji ? length(emoji) + 1 : 0);
                                            setName(Array.from(e.target.value).slice(0, room).join(""));
                                            setError("");
                                        }}
                                    />
                                    <Field.ErrorText>{error}</Field.ErrorText>
                                </Field.Root>

                                <Field.Root>
                                    <Field.Label>Emoji</Field.Label>
                                    <EmojiGrid value={emoji} onChange={setEmoji} />
                                    <Text fontSize="xs" color="fg.muted">
                                        Aparece na frente do nome. É opcional.
                                    </Text>
                                </Field.Root>

                                <Field.Root required>
                                    <RequiredLabel>Grupo</RequiredLabel>
                                    <NativeSelect.Root>
                                        <NativeSelect.Field value={groupId} onChange={(e) => setGroupId(e.target.value)}>
                                            {groups.map((group) => (
                                                <option key={group.id} value={group.id}>{group.name}</option>
                                            ))}
                                        </NativeSelect.Field>
                                        <NativeSelect.Indicator />
                                    </NativeSelect.Root>
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

// The family's categories under their groups: the default ones (which cannot be changed) and its own.
export default function AccountCategories() {
    const [categories, setCategories] = useState([]);
    const [groups, setGroups] = useState([]);
    const [loading, setLoading] = useState(true);
    const [failed, setFailed] = useState(false);
    const [drawer, setDrawer] = useState({ open: false, category: null, groupId: null }); // groupId: where a new one goes
    const [deleting, setDeleting] = useState(false);
    const [confirming, setConfirming] = useState(null); // the id of the category waiting for "Apagar" to be confirmed

    const load = useCallback(async () => {
        const token = getToken();
        if (!token) {
            setLoading(false);
            return;
        }
        const [list, groupList] = await Promise.all([getAllCategories(token), getCategoryGroups(token)]);
        if (!list || !list.data || !groupList.ok) {
            setFailed(true);
        } else {
            setFailed(false);
            setCategories(list.data);
            setGroups(groupList.data);
        }
        setLoading(false);
    }, []);

    useEffect(() => {
        load();
    }, [load]);

    const handleDelete = async (category) => {
        if (deleting) return; // a double click must not send the request twice
        setDeleting(true);
        const result = await deleteCategory(category.id, getToken());
        setConfirming(null);
        setDeleting(false);
        if (result.ok) {
            customToaster("Apagada", "success", `A categoria "${category.name}" foi apagada.`);
        } else if (result.status === 409) {
            customToaster("Não foi possível apagar", "error", result.detail); // says how many transactions use it
        } else if (result.status !== 404) {
            customToaster("Erro", "error", "Não foi possível apagar a categoria. Tente novamente.");
        }
        load();
    };

    if (loading) {
        return <Spinner size="xl" />;
    }
    if (failed) {
        return <Text color="fg.error">Não foi possível carregar as categorias. Tente novamente mais tarde.</Text>;
    }

    return (
        <Stack gap={8} maxW="3xl">
            <PageHeading title="Categorias">
                As categorias padrão servem para todos e não podem ser mudadas. As suas você pode criar em
                qualquer grupo, renomear, mudar de grupo e apagar (se nenhuma transação usar).
            </PageHeading>

            {groups.map((group) => {
                const inGroup = categories.filter((category) => category.group_id === group.id).sort(compareCategories);
                return (
                    <Box key={group.id} as="section" aria-label={group.name} borderWidth="1px" borderRadius="lg" overflow="hidden">
                        <HStack px={4} py={2} bg="bg.muted" justify="space-between">
                            <HStack gap={3}>
                                <Heading size="md">{group.name}</Heading>
                                <Text fontSize="sm" color="fg.muted">{inGroup.length}</Text>
                            </HStack>
                            <Button
                                size="xs"
                                variant="outline"
                                aria-label={`Adicionar em ${group.name}`}
                                onClick={() => setDrawer({ open: true, category: null, groupId: group.id })}
                            >
                                <LuPlus /> Adicionar
                            </Button>
                        </HStack>
                        {inGroup.length === 0 && (
                            <Text px={4} py={3} borderTopWidth="1px" color="fg.muted" fontSize="sm">
                                Nenhuma categoria neste grupo ainda.
                            </Text>
                        )}
                        <Stack as="ul" listStyleType="none" gap={0} m={0} p={0} aria-label={`Categorias de ${group.name}`}>
                            {inGroup.map((category) => (
                                <HStack
                                    as="li"
                                    key={category.id}
                                    gap={3}
                                    justify="space-between"
                                    px={4}
                                    py={2}
                                    minH="12"
                                    borderTopWidth="1px"
                                    _hover={{ bg: "bg.subtle" }}
                                >
                                    <HStack gap={3}>
                                        <Text fontWeight="medium">{category.name}</Text>
                                        {category.is_default && <Badge>Padrão</Badge>}
                                    </HStack>
                                    {!category.is_default &&
                                        (confirming === category.id ? (
                                            <HStack gap={2}>
                                                <Text fontSize="sm">Apagar &ldquo;{category.name}&rdquo;?</Text>
                                                <Button size="xs" colorPalette="red" onClick={() => handleDelete(category)}>
                                                    Apagar
                                                </Button>
                                                <Button size="xs" variant="outline" onClick={() => setConfirming(null)}>
                                                    Não apagar
                                                </Button>
                                            </HStack>
                                        ) : (
                                            <HStack gap={1}>
                                                <Button
                                                    size="xs"
                                                    variant="ghost"
                                                    aria-label={`Editar ${category.name}`}
                                                    onClick={() => setDrawer({ open: true, category, groupId: null })}
                                                >
                                                    <LuPencil />
                                                </Button>
                                                <Button
                                                    size="xs"
                                                    variant="ghost"
                                                    aria-label={`Apagar ${category.name}`}
                                                    onClick={() => setConfirming(category.id)}
                                                >
                                                    <LuTrash2 />
                                                </Button>
                                            </HStack>
                                        ))}
                                </HStack>
                            ))}
                        </Stack>
                    </Box>
                );
            })}

            <CategoryDrawer
                open={drawer.open}
                onClose={() => setDrawer((current) => ({ ...current, open: false }))}
                groups={groups}
                category={drawer.category}
                defaultGroupId={drawer.groupId}
                onSaved={load}
            />
        </Stack>
    );
}
