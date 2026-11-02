import { useEffect, useState } from "react";
import { Button, Code, Heading, List, RadioGroup, Separator, Stack, Table, Tag, Text, Wrap } from "@chakra-ui/react";
import { LuDownload } from "react-icons/lu";
import { exportTransactions, getAllCategories } from "../api/endpoints";
import { getToken } from "../lib/auth";
import { exportFileName, saveBlob } from "../lib/download";
import customToaster from "../utils/customToaster";

// The columns a spreadsheet must have to be imported. The first row holds these exact names.
// The import itself is not built yet; this page already tells people what it will expect.
const COLUMNS = [
    { name: "Data", required: true, format: "DD/MM/AAAA, não pode ser no futuro", example: "15/03/2026" },
    { name: "Descrição", required: true, format: "Texto, até 25 caracteres", example: "Almoço" },
    { name: "Categoria", required: true, format: "Uma das categorias listadas abaixo", example: "Alimentação" },
    { name: "Valor", required: true, format: "Maior que zero, com vírgula e duas casas decimais", example: "1.234,56" },
    { name: "Tipo", required: false, format: "Débito ou Crédito (se vazio, Débito)", example: "Débito" },
];

const EXPORT_FORMATS = [
    { value: "xlsx", label: "Excel (.xlsx)" },
    { value: "csv", label: "CSV (.csv)" },
];

// The export works; the bulk import is not built yet (this page already says what it will expect).
export default function AccountData() {
    const [categories, setCategories] = useState([]);
    const [exportFormat, setExportFormat] = useState("xlsx");
    const [exporting, setExporting] = useState(false);

    useEffect(() => {
        const token = getToken();
        if (!token) return;
        getAllCategories(token).then((data) => {
            if (data && data.data) setCategories(data.data);
        });
    }, []);

    const handleExport = async () => {
        setExporting(true);
        const result = await exportTransactions(exportFormat, getToken());
        setExporting(false);

        if (result && result.ok) {
            saveBlob(result.blob, exportFileName(exportFormat));
            customToaster("Pronto", "success", "O arquivo foi baixado.");
        } else {
            customToaster("Erro", "error", "Não foi possível exportar as transações. Tente novamente.");
        }
    };

    const categoryNames = categories.map((category) => category.name).sort((a, b) => a.localeCompare(b, "pt-BR"));

    return (
        <Stack gap={6} maxW="3xl">
            <Stack gap={1}>
                <Heading size="xl">Importar e exportar</Heading>
                <Text color="fg.muted">Leve suas transações para outro lugar, ou traga-as de uma planilha.</Text>
            </Stack>

            <Stack gap={4}>
                <Heading size="md">Importar</Heading>
                <Text color="fg.muted">
                    Em breve: envie uma planilha para cadastrar várias transações de uma vez. Prepare o arquivo
                    neste formato:
                </Text>

                <List.Root gap={1} color="fg.muted" fontSize="sm" ps={5}>
                    <List.Item>Arquivo <Code>.xlsx</Code> (Excel, primeira planilha) ou <Code>.csv</Code> em UTF-8, separado por ponto e vírgula (;) ou vírgula (,).</List.Item>
                    <List.Item>A primeira linha tem os nomes das colunas, exatamente como abaixo. A ordem não importa.</List.Item>
                    <List.Item>Cada linha seguinte é uma transação. Linhas com problema são apontadas e as outras não são importadas até você corrigi-las.</List.Item>
                </List.Root>

                <Table.ScrollArea>
                    <Table.Root size="sm" aria-label="Colunas da planilha de importação">
                        <Table.Header>
                            <Table.Row>
                                <Table.ColumnHeader>Coluna</Table.ColumnHeader>
                                <Table.ColumnHeader>Obrigatória</Table.ColumnHeader>
                                <Table.ColumnHeader>Formato</Table.ColumnHeader>
                                <Table.ColumnHeader>Exemplo</Table.ColumnHeader>
                            </Table.Row>
                        </Table.Header>
                        <Table.Body>
                            {COLUMNS.map((column) => (
                                <Table.Row key={column.name}>
                                    <Table.Cell fontWeight="semibold">{column.name}</Table.Cell>
                                    <Table.Cell>{column.required ? "Sim" : "Não"}</Table.Cell>
                                    <Table.Cell color="fg.muted">{column.format}</Table.Cell>
                                    <Table.Cell><Code>{column.example}</Code></Table.Cell>
                                </Table.Row>
                            ))}
                        </Table.Body>
                    </Table.Root>
                </Table.ScrollArea>

                {categoryNames.length > 0 && (
                    <Stack gap={2}>
                        <Text fontSize="sm" fontWeight="semibold">Categorias aceitas</Text>
                        <Wrap aria-label="Categorias aceitas">
                            {categoryNames.map((name) => (
                                <Tag.Root key={name}><Tag.Label>{name}</Tag.Label></Tag.Root>
                            ))}
                        </Wrap>
                    </Stack>
                )}
            </Stack>

            <Separator />

            <Stack gap={4}>
                <Heading size="md">Exportar</Heading>
                <Text color="fg.muted">
                    Baixe todas as suas transações, da mais nova para a mais antiga, com as mesmas colunas da
                    importação. O valor sai sempre positivo; se foi entrada ou saída está na coluna Tipo.
                </Text>

                <RadioGroup.Root value={exportFormat} onValueChange={(e) => setExportFormat(e.value)}>
                    <Stack direction="row" gap={6}>
                        {EXPORT_FORMATS.map((format) => (
                            <RadioGroup.Item key={format.value} value={format.value}>
                                <RadioGroup.ItemHiddenInput />
                                <RadioGroup.ItemIndicator />
                                <RadioGroup.ItemText>{format.label}</RadioGroup.ItemText>
                            </RadioGroup.Item>
                        ))}
                    </Stack>
                </RadioGroup.Root>

                <Button alignSelf="start" onClick={handleExport} loading={exporting}>
                    <LuDownload /> Baixar
                </Button>
            </Stack>
        </Stack>
    );
}
