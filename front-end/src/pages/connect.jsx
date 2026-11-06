import { useEffect, useState } from "react";
import { Alert, Button, Center, Heading, List, Stack, Text } from "@chakra-ui/react";
import { Navigate, useLocation } from "react-router-dom";
import { decideConnection } from "../api/endpoints";
import { getToken, isAuthenticated } from "../lib/auth";
import { leaveTo, readConnectRequest, rememberPendingConnect } from "../lib/connect";

// Where an AI app (the Claude app) asks the person to let it add transactions for them. The person signs in as usual,
// then says yes or no; either way they are sent back to the app.
export default function Connect() {
    const { search } = useLocation();
    const asked = readConnectRequest(search);
    const signedIn = isAuthenticated();
    const [sending, setSending] = useState(false);
    const [failed, setFailed] = useState(false);

    useEffect(() => {
        if (asked && !signedIn) rememberPendingConnect(search);
    }, [asked, signedIn, search]);

    if (!asked) {
        return (
            <Center minH="100dvh" px={6}>
                <Alert.Root status="warning" maxW="md" borderRadius="lg">
                    <Alert.Indicator />
                    <Alert.Description>
                        Esta página abre quando um aplicativo (como o Claude) pede acesso. Abra-a pelo aplicativo.
                    </Alert.Description>
                </Alert.Root>
            </Center>
        );
    }
    if (!signedIn) return <Navigate to="/login-google" replace />;

    const answer = async (allow) => {
        setSending(true);
        setFailed(false);
        const result = await decideConnection({ ...asked.request, allow }, getToken());
        if (result.ok) {
            leaveTo(result.data.redirect_to);
        } else {
            setFailed(true);
            setSending(false);
        }
    };

    return (
        <Center minH="100dvh" px={6}>
            <Stack gap={6} maxW="md" w="full">
                <Stack gap={2}>
                    <Heading size="2xl">Conectar {asked.app}?</Heading>
                    <Text color="fg.muted">
                        <strong>{asked.app}</strong> quer usar o Money Budget como você. Com a sua permissão, ele poderá:
                    </Text>
                </Stack>
                <List.Root gap={1} ps={5}>
                    <List.Item>ver as categorias da sua família;</List.Item>
                    <List.Item>mostrar as transações que ele leu de uma foto ou extrato e adicioná-las depois que você confirmar.</List.Item>
                </List.Root>
                <Text fontSize="sm" color="fg.muted">
                    Depois de responder, você volta para <strong>{asked.returnHost}</strong>. Só permita se esse endereço for do aplicativo que você está usando.
                </Text>
                <Text fontSize="sm" color="fg.muted">
                    Ele não consegue apagar nem alterar nada, nem ver suas transações. Você pode desconectar quando quiser em
                    Conta → Assistentes de IA.
                </Text>
                {failed && (
                    <Alert.Root status="error" borderRadius="lg">
                        <Alert.Indicator />
                        <Alert.Description>Não foi possível concluir. Volte ao aplicativo e tente conectar de novo.</Alert.Description>
                    </Alert.Root>
                )}
                <Stack direction={{ base: "column", sm: "row" }} gap={3}>
                    <Button flex={1} minH="44px" onClick={() => answer(true)} loading={sending}>
                        Permitir
                    </Button>
                    <Button flex={1} minH="44px" variant="outline" onClick={() => answer(false)} disabled={sending}>
                        Negar
                    </Button>
                </Stack>
            </Stack>
        </Center>
    );
}
