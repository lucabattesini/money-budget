import { useCallback, useEffect, useState } from "react";
import { Avatar, Badge, Box, Button, Code, Field, Heading, HStack, Input, RadioGroup, Separator, Spinner, Stack, Text } from "@chakra-ui/react";
import { LuCopy } from "react-icons/lu";
import { cancelInvite, createInvite, getFamily, getInvites, joinFamily } from "../api/endpoints";
import { getToken } from "../lib/auth";
import customToaster from "../utils/customToaster";

const ROLE_NAMES = { owner: "Dono", member: "Membro" };

const JOIN_CHOICES = [
    { value: "bring", label: "Trazer meus dados", hint: "Minhas transações e categorias passam a fazer parte da nova família." },
    { value: "empty", label: "Começar vazio", hint: "Só vejo os dados da nova família. Os meus ficam guardados, sem aparecer." },
];

const formatDate = (iso) => new Date(iso).toLocaleDateString("pt-BR");

// The people who share this budget, the invite codes (owner only) and a field to join another family.
export default function AccountFamily() {
    const [family, setFamily] = useState(null);
    const [invites, setInvites] = useState([]);
    const [newCode, setNewCode] = useState(null); // shown once, right after it is created
    const [loading, setLoading] = useState(true);
    const [failed, setFailed] = useState(false);
    const [code, setCode] = useState("");
    const [choice, setChoice] = useState("");
    const [joining, setJoining] = useState(false);

    const load = useCallback(async () => {
        const token = getToken();
        if (!token) {
            setLoading(false);
            return;
        }
        const mine = await getFamily(token);
        if (!mine.ok) {
            setFailed(true);
            setLoading(false);
            return;
        }
        setFailed(false);
        setFamily(mine.data);
        if (mine.data.role === "owner") {
            const active = await getInvites(token);
            setInvites(active.ok ? active.data : []);
        } else {
            setInvites([]);
        }
        setLoading(false);
    }, []);

    useEffect(() => {
        load();
    }, [load]);

    const handleCreate = async () => {
        const result = await createInvite(getToken());
        if (!result.ok) {
            customToaster("Erro", "error", result.detail || "Não foi possível criar o código. Tente novamente.");
            return;
        }
        setNewCode(result.data.code);
        load();
    };

    const handleCopy = async () => {
        try {
            await navigator.clipboard.writeText(newCode);
            customToaster("Copiado", "success", "O código está na sua área de transferência.");
        } catch {
            customToaster("Erro", "error", "Não foi possível copiar. Selecione o código e copie à mão.");
        }
    };

    const handleCancel = async (invite) => {
        const result = await cancelInvite(invite.id, getToken());
        if (!result.ok && result.status !== 404) {
            customToaster("Erro", "error", result.detail || "Não foi possível cancelar o código.");
            return;
        }
        load();
    };

    const handleJoin = async () => {
        setJoining(true);
        const result = await joinFamily(code.trim(), choice === "bring", getToken());
        setJoining(false);
        if (!result.ok) {
            customToaster("Erro", "error", result.detail || "Não foi possível entrar na família. Tente novamente.");
            return;
        }
        customToaster("Pronto", "success", "Você entrou na família.");
        setCode("");
        setChoice("");
        setNewCode(null);
        load();
    };

    if (loading) {
        return <Spinner size="xl" />;
    }
    if (failed || !family) {
        return <Text color="fg.error">Não foi possível carregar a sua família. Tente novamente mais tarde.</Text>;
    }

    const isOwner = family.role === "owner";

    return (
        <Stack gap={8} maxW="3xl">
            <Stack gap={1}>
                <Heading size="xl">Família</Heading>
                <Text color="fg.muted">As pessoas da família veem e editam as mesmas transações e categorias.</Text>
            </Stack>

            <Stack gap={3}>
                <Heading size="md">Pessoas</Heading>
                <Stack as="ul" listStyleType="none" gap={2} aria-label="Pessoas da família">
                    {family.members.map((member) => (
                        <HStack as="li" key={member.id} gap={3}>
                            <Avatar.Root size="sm">
                                <Avatar.Fallback name={member.name} />
                                {member.picture && <Avatar.Image src={member.picture} />}
                            </Avatar.Root>
                            <Text>{member.name}</Text>
                            <Badge>{ROLE_NAMES[member.role] ?? member.role}</Badge>
                        </HStack>
                    ))}
                </Stack>
            </Stack>

            {isOwner && (
                <>
                    <Separator />
                    <Stack gap={4}>
                        <Heading size="md">Convidar</Heading>
                        <Text color="fg.muted">
                            Gere um código e envie para quem vai entrar. Cada código vale uma vez só e vence em 7 dias.
                        </Text>
                        <Button alignSelf="start" onClick={handleCreate}>Gerar código</Button>

                        {newCode && (
                            <Box borderWidth="1px" borderRadius="md" p={4} role="status">
                                <Stack gap={2}>
                                    <Text fontSize="sm" color="fg.muted">
                                        Novo código. Copie agora: por segurança ele não aparece de novo.
                                    </Text>
                                    <HStack gap={3}>
                                        <Code fontSize="lg" data-testid="new-code">{newCode}</Code>
                                        <Button size="xs" variant="outline" onClick={handleCopy}><LuCopy /> Copiar</Button>
                                    </HStack>
                                </Stack>
                            </Box>
                        )}

                        {invites.length > 0 && (
                            <Stack gap={2}>
                                <Text fontSize="sm" fontWeight="semibold">Códigos ativos</Text>
                                <Stack as="ul" listStyleType="none" gap={2} aria-label="Códigos ativos">
                                    {invites.map((invite) => (
                                        <HStack as="li" key={invite.id} gap={3} justify="space-between">
                                            <Text fontSize="sm">
                                                Código terminado em <Code>{invite.code_hint}</Code>, vence em {formatDate(invite.expires_at)}
                                            </Text>
                                            <Button
                                                size="xs"
                                                variant="outline"
                                                aria-label={`Cancelar código terminado em ${invite.code_hint}`}
                                                onClick={() => handleCancel(invite)}
                                            >
                                                Cancelar
                                            </Button>
                                        </HStack>
                                    ))}
                                </Stack>
                            </Stack>
                        )}
                    </Stack>
                </>
            )}

            <Separator />

            <Stack gap={4}>
                <Heading size="md">Entrar em uma família</Heading>
                <Text color="fg.muted">
                    Recebeu um código? Escolha o que fazer com os seus dados e entre. Quem já está numa família com
                    outras pessoas precisa sair dela antes.
                </Text>

                <Field.Root maxW="sm">
                    <Field.Label>Código de convite</Field.Label>
                    <Input value={code} onChange={(e) => setCode(e.target.value)} placeholder="XXXX-XXXX-XXXX-XXXX" autoComplete="off" />
                </Field.Root>

                <RadioGroup.Root value={choice} onValueChange={(e) => setChoice(e.value)}>
                    <Stack gap={3}>
                        {JOIN_CHOICES.map((option) => (
                            <RadioGroup.Item key={option.value} value={option.value}>
                                <RadioGroup.ItemHiddenInput />
                                <RadioGroup.ItemIndicator />
                                <Stack gap={0}>
                                    <RadioGroup.ItemText>{option.label}</RadioGroup.ItemText>
                                    <Text fontSize="sm" color="fg.muted">{option.hint}</Text>
                                </Stack>
                            </RadioGroup.Item>
                        ))}
                    </Stack>
                </RadioGroup.Root>

                <Button alignSelf="start" onClick={handleJoin} loading={joining} disabled={!code.trim() || !choice}>
                    Entrar na família
                </Button>
            </Stack>
        </Stack>
    );
}
