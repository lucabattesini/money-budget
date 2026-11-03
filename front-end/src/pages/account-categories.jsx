import { useCallback, useEffect, useState } from "react";
import { Badge, Button, CloseButton, Drawer, Field, HStack, Heading, Input, NativeSelect, Portal, Spinner, Stack, Text } from "@chakra-ui/react";
import { LuPencil, LuPlus, LuTrash2 } from "react-icons/lu";
import { createCategory, deleteCategory, getAllCategories, getCategoryGroups, updateCategory } from "../api/endpoints";
import { getToken } from "../lib/auth";
import customToaster from "../utils/customToaster";

const MAX_NAME = 100;
const FALLBACK_GROUP = "Outros";

const byName = (a, b) => a.name.localeCompare(b.name, "pt-BR");

// A label with a red asterisk, like the transaction form.
function RequiredLabel({ children }) {
    return <Field.Label _after={{ content: '" *"', color: "red.500", fontWeight: "bold" }}>{children}</Field.Label>;
}

// Side panel to add a category, or to edit `category` (its name and group).
function CategoryDrawer({ open, onClose, groups, category, onSaved }) {
    const editing = category !== null;
    const [name, setName] = useState("");
    const [groupId, setGroupId] = useState("");
    const [error, setError] = useState("");
    const [saving, setSaving] = useState(false);

    // Start from the category being edited (or empty, in "Outros") every time the panel opens
    useEffect(() => {
        if (open) {
            setName(editing ? category.name : "");
            const fallback = groups.find((group) => group.name === FALLBACK_GROUP);
            setGroupId(String(editing ? category.group_id : fallback?.id ?? ""));
            setError("");
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [open, category]);

    const handleSubmit = async (event) => {
        event.preventDefault();
        if (!name.trim()) {
            setError("O nome da categoria não pode ficar vazio.");
            return;
        }
        setSaving(true);
        const payload = { name: name.trim(), group_id: Number(groupId) };
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
                                        maxLength={MAX_NAME}
                                        value={name}
                                        onChange={(e) => {
                                            setName(e.target.value);
                                            setError("");
                                        }}
                                    />
                                    <Field.ErrorText>{error}</Field.ErrorText>
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
    const [drawer, setDrawer] = useState({ open: false, category: null });
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
        const result = await deleteCategory(category.id, getToken());
        setConfirming(null);
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
            <HStack justify="space-between" align="start" gap={4}>
                <Stack gap={1}>
                    <Heading size="xl">Categorias</Heading>
                    <Text color="fg.muted">
                        As categorias padrão servem para todos e não podem ser mudadas. As suas você pode criar,
                        renomear, mudar de grupo e apagar (se nenhuma transação usar).
                    </Text>
                </Stack>
                <Button onClick={() => setDrawer({ open: true, category: null })} flexShrink={0}>
                    <LuPlus /> Nova categoria
                </Button>
            </HStack>

            {groups.map((group) => {
                const inGroup = categories.filter((category) => category.group_id === group.id).sort(byName);
                if (inGroup.length === 0) return null;
                return (
                    <Stack key={group.id} gap={2} as="section" aria-label={group.name}>
                        <Heading size="md">{group.name}</Heading>
                        <Stack as="ul" listStyleType="none" gap={1} aria-label={`Categorias de ${group.name}`}>
                            {inGroup.map((category) => (
                                <HStack as="li" key={category.id} gap={3} justify="space-between" minH="9">
                                    <HStack gap={3}>
                                        <Text>{category.name}</Text>
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
                                                    onClick={() => setDrawer({ open: true, category })}
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
                    </Stack>
                );
            })}

            <CategoryDrawer
                open={drawer.open}
                onClose={() => setDrawer((current) => ({ ...current, open: false }))}
                groups={groups}
                category={drawer.category}
                onSaved={load}
            />
        </Stack>
    );
}
