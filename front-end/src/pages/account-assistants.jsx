import { useCallback, useEffect, useState } from "react";
import { Button, Code, Heading, List, Spinner, Stack, Table, Text } from "@chakra-ui/react";
import { LuUnplug } from "react-icons/lu";
import { API_URL } from "../api/config";
import { disconnectApp, getConnections } from "../api/endpoints";
import { getToken } from "../lib/auth";
import customToaster from "../utils/customToaster";

const dateOf = (iso) => (iso ? new Date(iso + "Z").toLocaleDateString("pt-BR") : "—");

// The AI apps (the Claude app) the person let add transactions for them, with a way to disconnect each.
export default function AccountAssistants() {
    const [connections, setConnections] = useState([]);
    const [loading, setLoading] = useState(true);
    const [failed, setFailed] = useState(false);
    const address = `${API_URL || window.location.origin}/mcp`;

    const load = useCallback(async () => {
        const result = await getConnections(getToken());
        if (result.ok) setConnections(result.data);
        else setFailed(true);
        setLoading(false);
    }, []);

    useEffect(() => {
        load();
    }, [load]);

    const disconnect = async (connection) => {
        const result = await disconnectApp(connection.id, getToken());
        if (result.ok) customToaster("Pronto", "success", `${connection.app} foi desconectado.`);
        else customToaster("Erro", "error", result.detail || "Não foi possível desconectar. Tente novamente.");
        load();
    };

    return (
        <Stack gap={6} maxW="3xl">
            <Stack gap={1}>
                <Heading size="xl">Assistentes de IA</Heading>
                <Text color="fg.muted">
                    Mande uma foto de um recibo ou um extrato para o Claude e ele cadastra as transações aqui, depois que você confirmar.
                </Text>
            </Stack>

            <Stack gap={3}>
                <Heading size="md">Como conectar</Heading>
                <List.Root as="ol" gap={1} color="fg.muted" fontSize="sm" ps={5}>
                    <List.Item>No app do Claude, abra as configurações de conectores e adicione um conector personalizado.</List.Item>
                    <List.Item>Use este endereço: <Code>{address}</Code></List.Item>
                    <List.Item>Entre com a sua conta Google quando o app pedir e permita o acesso.</List.Item>
                    <List.Item>Em uma conversa, envie a foto ou o PDF. O Claude mostra o que leu e só adiciona depois da sua confirmação.</List.Item>
                </List.Root>
                <Text fontSize="sm" color="fg.muted">
                    Transações que você já tem (mesmo dia, descrição, valor, categoria e tipo) são ignoradas, então enviar o mesmo extrato duas vezes não duplica nada.
                </Text>
            </Stack>

            <Stack gap={3}>
                <Heading size="md">Conectados</Heading>
                {loading && <Spinner />}
                {failed && <Text color="fg.error">Não foi possível carregar as conexões. Tente novamente mais tarde.</Text>}
                {!loading && !failed && connections.length === 0 && <Text color="fg.muted">Nenhum aplicativo conectado.</Text>}
                {connections.length > 0 && (
                    <Table.ScrollArea>
                        <Table.Root size="sm" aria-label="Aplicativos conectados">
                            <Table.Header>
                                <Table.Row>
                                    <Table.ColumnHeader>Aplicativo</Table.ColumnHeader>
                                    <Table.ColumnHeader>Conectado em</Table.ColumnHeader>
                                    <Table.ColumnHeader>Último uso</Table.ColumnHeader>
                                    <Table.ColumnHeader />
                                </Table.Row>
                            </Table.Header>
                            <Table.Body>
                                {connections.map((connection) => (
                                    <Table.Row key={connection.id}>
                                        <Table.Cell fontWeight="semibold">{connection.app}</Table.Cell>
                                        <Table.Cell>{dateOf(connection.connected_at)}</Table.Cell>
                                        <Table.Cell>{dateOf(connection.last_used_at)}</Table.Cell>
                                        <Table.Cell textAlign="end">
                                            <Button size="sm" variant="outline" onClick={() => disconnect(connection)} aria-label={`Desconectar ${connection.app}`}>
                                                <LuUnplug /> Desconectar
                                            </Button>
                                        </Table.Cell>
                                    </Table.Row>
                                ))}
                            </Table.Body>
                        </Table.Root>
                    </Table.ScrollArea>
                )}
            </Stack>
        </Stack>
    );
}
