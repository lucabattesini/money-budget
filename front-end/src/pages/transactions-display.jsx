import { Fragment, useState, useEffect } from "react";
import { Center, Stack, Flex, Text, IconButton, Button, Box, Table, Menu, Portal } from "@chakra-ui/react";
import { getTransactions, getAllCategories, deleteTransaction } from "../api/endpoints";
import { getToken } from "../lib/auth";
import { formatCents } from "../lib/money";
import customToaster from "../utils/customToaster";
import { SpinnerLoading } from "../components/spinnerLoading";
import TransactionSummary from "../components/TransactionSummary";
import AddTransactionDrawer from "../components/AddTransactionDrawer";
import { Toaster } from "../components/ui/toaster";
import { LuEllipsisVertical, LuPlus, LuTrash2 } from "react-icons/lu";

export default function TransactionsDisplay() {
    const [loading, setLoading] = useState(true);
    const [categories, setCategories] = useState([]);
    const [transactions, setTransactions] = useState([]);
    const [trigger, setTrigger] = useState(0);
    const [adding, setAdding] = useState(false);

    useEffect(() => {
        const token = getToken();
        Promise.all([
            getAllCategories(token),
            getTransactions({"organized_by": null, "date": null}, token)
        ]).then(([categoriesData, transactionsData]) => {
            if (categoriesData) setCategories(categoriesData.data);
            if (transactionsData) setTransactions(transactionsData.data);
            setLoading(false);
        });
    }, [trigger]);

    const reload = () => setTrigger((current) => current + 1);

    // Wait for the delete to finish before reloading, otherwise the list can still show the row
    const onDelete = async (id) => {
        const response = await deleteTransaction(id, getToken());
        if (!response || !response.ok) {
            customToaster("Erro", "error", "Não foi possível excluir a transação.");
        }
        reload();
    }

    const today = [];
    const thisWeek = [];
    const thisMonth = [];
    const older = [];

    const now = new Date();
    // Start of today
    const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    
    // Start of this week (last 7 days)
    const startOfWeek = new Date(startOfToday);
    startOfWeek.setDate(startOfWeek.getDate() - 7);

    // Start of this month
    const startOfMonth = new Date(now.getFullYear(), now.getMonth(), 1);

    transactions.forEach(transaction => {
        const tDate = new Date(transaction.transactioned_at);
        if (tDate >= startOfToday) {
            today.push(transaction);
        } else if (tDate >= startOfWeek) {
            thisWeek.push(transaction);
        } else if (tDate >= startOfMonth) {
            thisMonth.push(transaction);
        } else {
            older.push(transaction);
        }
    });

    const groups = [
        { title: "Hoje", data: today },
        { title: "Esta Semana", data: thisWeek },
        { title: "Este Mês", data: thisMonth },
        { title: "Todo o Resto", data: older },
    ];

    const categoryName = (transaction) =>
        categories?.find((category) => category.id === transaction.category_id)?.name ?? "Categoria não encontrada";

    const renderRow = (transaction) => (
        <Table.Row key={transaction.id}>
            <Table.Cell whiteSpace="nowrap">{new Date(transaction.transactioned_at).toLocaleDateString("pt-BR")}</Table.Cell>
            <Table.Cell wordBreak="break-word">{transaction.label}</Table.Cell>
            <Table.Cell color="fg.muted">{categoryName(transaction)}</Table.Cell>
            <Table.Cell textAlign="end" whiteSpace="nowrap">{formatCents(transaction.value)}</Table.Cell>
            <Table.Cell textAlign="end" width="1%">
                <Menu.Root positioning={{ placement: "bottom-end" }}>
                    <Menu.Trigger asChild>
                        <IconButton variant="ghost" size="xs" aria-label={`Ações para ${transaction.label}`}>
                            <LuEllipsisVertical />
                        </IconButton>
                    </Menu.Trigger>
                    <Portal>
                        <Menu.Positioner>
                            <Menu.Content>
                                <Menu.Item value="delete" color="fg.error" onClick={() => onDelete(transaction.id)}>
                                    <LuTrash2 /> Excluir
                                </Menu.Item>
                            </Menu.Content>
                        </Menu.Positioner>
                    </Portal>
                </Menu.Root>
            </Table.Cell>
        </Table.Row>
    );

    const visibleGroups = groups.filter((group) => group.data.length > 0);

    return(
        <Center>
            <Toaster />
            <Stack minHeight="100vh" gap={6} w="full" maxW="4xl" align="center" justify="flex-start" py={10} px={4}>
                <TransactionSummary transactions={transactions} />

                <Flex w="full" justify="space-between" align="center">
                    <Text fontSize="lg" fontWeight="bold">Transações</Text>
                    <Button size="sm" onClick={() => setAdding(true)}>
                        <LuPlus /> Adicionar
                    </Button>
                </Flex>

                {loading && <SpinnerLoading/>}

                {!loading && visibleGroups.length > 0 && (
                    <Table.ScrollArea w="full">
                        <Table.Root size="sm">
                            <Table.Header>
                                <Table.Row>
                                    <Table.ColumnHeader>Data</Table.ColumnHeader>
                                    <Table.ColumnHeader>Descrição</Table.ColumnHeader>
                                    <Table.ColumnHeader>Categoria</Table.ColumnHeader>
                                    <Table.ColumnHeader textAlign="end">Valor</Table.ColumnHeader>
                                    <Table.ColumnHeader />
                                </Table.Row>
                            </Table.Header>
                            <Table.Body>
                                {visibleGroups.map((group) => (
                                    <Fragment key={group.title}>
                                        <Table.Row>
                                            <Table.Cell colSpan={5} pt={6}>
                                                <Box color="gray.400" fontSize="xs" fontWeight="bold" textTransform="uppercase">
                                                    {group.title}
                                                </Box>
                                            </Table.Cell>
                                        </Table.Row>
                                        {group.data.map(renderRow)}
                                    </Fragment>
                                ))}
                            </Table.Body>
                        </Table.Root>
                    </Table.ScrollArea>
                )}

                {!loading && visibleGroups.length === 0 && (
                    <Text color="fg.muted">Nenhuma transação ainda.</Text>
                )}
            </Stack>

            <AddTransactionDrawer
                open={adding}
                onClose={() => setAdding(false)}
                categories={categories}
                onSaved={reload}
            />
        </Center>
    )
}
