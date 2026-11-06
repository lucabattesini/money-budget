import { useEffect, useState } from "react";
import { Button, Code, Heading, List, RadioGroup, Separator, Stack, Table, Tag, Text, Wrap } from "@chakra-ui/react";
import { LuDownload, LuUpload } from "react-icons/lu";
import { getAllCategories } from "../api/endpoints";
import { getToken } from "../lib/auth";
import { compareNames } from "../lib/categoryName";
import ImportDialog from "../components/ImportDialog";
import { enqueueExport, followExport } from "../lib/exportJobs";

// The columns a spreadsheet must have to be imported. The first row holds these exact names.
const COLUMNS = [
    { name: "Data", required: true, format: "DD/MM/AAAA, MM/DD/AAAA ou AAAA-MM-DD; não pode ser no futuro", example: "15/03/2026" },
    { name: "Descrição", required: true, format: "Texto, até 100 caracteres", example: "Almoço" },
    { name: "Categoria", required: true, format: "Uma categoria; as que você ainda não tem podem ser criadas na importação", example: "Restaurantes e Bares" },
    { name: "Valor", required: true, format: "Zero ou mais, no máximo duas casas decimais: 1.234,56 ou 1,234.56. Pode vir negativo (veja o sinal)", example: "1.234,56" },
    { name: "Tipo", required: false, format: "Débito ou Crédito (se vazio, Débito). Dispensável se o sinal do valor já diz", example: "Débito" },
    { name: "Pessoa", required: false, format: "Nome de alguém da sua família (se vazio, quem está importando)", example: "Bia Souza" },
];

const EXPORT_FORMATS = [
    { value: "xlsx", label: "Excel (.xlsx)" },
    { value: "csv", label: "CSV (.csv)" },
];

// Bring transactions in from a spreadsheet (in steps, in a dialog) and take them out as a file.
export default function AccountData() {
    const [categories, setCategories] = useState([]);
    const [exportFormat, setExportFormat] = useState("xlsx");
    const [queueing, setQueueing] = useState(false);
    const [importing, setImporting] = useState(false); // the import dialog is open

    useEffect(() => {
        const token = getToken();
        if (!token) return;
        getAllCategories(token).then((data) => {
            if (data && data.data) setCategories(data.data);
        });
    }, []);

    // Queue the export and move on: the file is built in the background and downloaded when it is ready,
    // even if the user goes to another page meanwhile.
    const handleExport = async () => {
        setQueueing(true);
        const job = await enqueueExport(exportFormat);
        setQueueing(false);
        if (job) followExport(job);
    };

    const categoryNames = categories.map((category) => category.name).sort(compareNames);

    return (
        <Stack gap={6} maxW="3xl">
            <Stack gap={1}>
                <Heading size="xl">Importar e exportar</Heading>
                <Text color="fg.muted">Leve suas transações para outro lugar, ou traga-as de uma planilha.</Text>
            </Stack>

            <Stack gap={4}>
                <Heading size="md">Importar</Heading>
                <Text color="fg.muted">
                    Envie uma planilha para cadastrar várias transações de uma vez. Prepare o arquivo neste formato:
                </Text>

                <List.Root gap={1} color="fg.muted" fontSize="sm" ps={5}>
                    <List.Item>Arquivo <Code>.xlsx</Code> (Excel, primeira planilha) ou <Code>.csv</Code> em UTF-8, separado por ponto e vírgula (;) ou vírgula (,).</List.Item>
                    <List.Item>A primeira linha tem os nomes das colunas e a ordem não importa. Na importação você diz qual coluna é qual (as que têm os nomes abaixo já vêm escolhidas) e como o arquivo escreve datas e valores.</List.Item>
                    <List.Item>O valor pode vir sempre positivo, com o débito ou crédito na coluna Tipo, ou com sinal: negativo é débito (ou o contrário, você escolhe).</List.Item>
                    <List.Item>Cada linha seguinte é uma transação. Se alguma linha tiver problema, nada é importado: mostramos todos os problemas para você corrigir e enviar de novo.</List.Item>
                    <List.Item>Transações que você já tem (mesmo dia, descrição, valor, categoria e tipo) são ignoradas, então enviar o mesmo arquivo duas vezes não duplica nada.</List.Item>
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

                <Button alignSelf="start" onClick={() => setImporting(true)}>
                    <LuUpload /> Importar planilha
                </Button>
                <ImportDialog open={importing} onClose={() => setImporting(false)} />

                {categoryNames.length > 0 && (
                    <Stack gap={2}>
                        <Text fontSize="sm" fontWeight="semibold">Categorias que você já tem</Text>
                        <Wrap aria-label="Categorias que você já tem">
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
                    importação. O valor sai sempre positivo; se foi entrada ou saída está na coluna Tipo, e de quem é a transação, na coluna Pessoa.
                    O arquivo é gerado em segundo plano: você pode continuar usando o app e avisamos quando
                    estiver pronto.
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

                <Button alignSelf="start" onClick={handleExport} loading={queueing}>
                    <LuDownload /> Baixar
                </Button>
            </Stack>
        </Stack>
    );
}
