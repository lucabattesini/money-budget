import { useCallback, useEffect, useState } from "react";
import { Button, Heading, HStack, Input, Spinner, Stack, Text } from "@chakra-ui/react";
import { LuPencil, LuTrash2 } from "react-icons/lu";
import { deleteMerchant, getMerchants, renameMerchant } from "../api/endpoints";
import { getToken } from "../lib/auth";
import customToaster from "../utils/customToaster";

const MAX_NAME = 100; // the size of the database column

// The places and companies of the family (Uber, iFood...): rename them, and delete the ones no transaction uses.
// They are created by typing a new name in a transaction.
export default function AccountMerchants() {
    const [merchants, setMerchants] = useState([]);
    const [loading, setLoading] = useState(true);
    const [failed, setFailed] = useState(false);
    const [editing, setEditing] = useState(null); // { id, name }: the one being renamed
    const [confirming, setConfirming] = useState(null); // the id asking "are you sure?"

    const load = useCallback(async () => {
        const result = await getMerchants(getToken());
        if (result.ok) setMerchants(result.data);
        else setFailed(true);
        setLoading(false);
    }, []);

    useEffect(() => {
        load();
    }, [load]);

    const save = async (event) => {
        event.preventDefault();
        const result = await renameMerchant(editing.id, editing.name, getToken());
        if (result.ok) {
            setEditing(null);
            customToaster("Salvo", "success", "O estabelecimento foi renomeado.");
        } else {
            customToaster("Erro", "error", result.detail || "Não foi possível renomear. Tente novamente.");
        }
        load();
    };

    const remove = async (merchant) => {
        setConfirming(null);
        const result = await deleteMerchant(merchant.id, getToken());
        if (result.ok) customToaster("Pronto", "success", "O estabelecimento foi apagado.");
        else customToaster("Erro", "error", result.detail || "Não foi possível apagar. Tente novamente.");
        load();
    };

    if (loading) return <Spinner size="xl" />;
    if (failed) return <Text color="fg.error">Não foi possível carregar os estabelecimentos. Tente novamente mais tarde.</Text>;

    return (
        <Stack gap={6} maxW="3xl">
            <Stack gap={1}>
                <Heading size="xl">Estabelecimentos</Heading>
                <Text color="fg.muted">
                    Os lugares e empresas das suas transações. Para criar um, digite o nome ao registrar uma
                    transação. Aqui você pode renomear e apagar (se nenhuma transação usar).
                </Text>
            </Stack>

            {merchants.length === 0 ? (
                <Text color="fg.muted">Nenhum estabelecimento ainda.</Text>
            ) : (
                <Stack as="ul" listStyleType="none" gap={0} m={0} p={0} aria-label="Estabelecimentos" borderWidth="1px" borderRadius="lg" overflow="hidden">
                    {merchants.map((merchant) => (
                        <HStack as="li" key={merchant.id} gap={3} justify="space-between" px={4} py={2} minH="12" borderTopWidth="1px" _first={{ borderTopWidth: 0 }}>
                            {editing?.id === merchant.id ? (
                                <HStack as="form" gap={2} flex="1" onSubmit={save}>
                                    <Input
                                        size="sm"
                                        aria-label="Novo nome"
                                        maxLength={MAX_NAME}
                                        value={editing.name}
                                        onChange={(e) => setEditing({ ...editing, name: e.target.value })}
                                        autoFocus
                                    />
                                    <Button size="xs" type="submit">Salvar</Button>
                                    <Button size="xs" variant="outline" onClick={() => setEditing(null)}>Cancelar</Button>
                                </HStack>
                            ) : (
                                <>
                                    <HStack gap={3}>
                                        <Text fontWeight="medium">{merchant.name}</Text>
                                        <Text fontSize="sm" color="fg.muted">
                                            {merchant.transactions === 1 ? "1 transação" : `${merchant.transactions} transações`}
                                        </Text>
                                    </HStack>
                                    {confirming === merchant.id ? (
                                        <HStack gap={2}>
                                            <Text fontSize="sm">Apagar &ldquo;{merchant.name}&rdquo;?</Text>
                                            <Button size="xs" colorPalette="red" onClick={() => remove(merchant)}>Apagar</Button>
                                            <Button size="xs" variant="outline" onClick={() => setConfirming(null)}>Não apagar</Button>
                                        </HStack>
                                    ) : (
                                        <HStack gap={1}>
                                            <Button size="xs" variant="ghost" aria-label={`Renomear ${merchant.name}`}
                                                onClick={() => setEditing({ id: merchant.id, name: merchant.name })}>
                                                <LuPencil />
                                            </Button>
                                            <Button size="xs" variant="ghost" aria-label={`Apagar ${merchant.name}`}
                                                onClick={() => setConfirming(merchant.id)}>
                                                <LuTrash2 />
                                            </Button>
                                        </HStack>
                                    )}
                                </>
                            )}
                        </HStack>
                    ))}
                </Stack>
            )}
        </Stack>
    );
}
