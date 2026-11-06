import { useEffect, useRef, useState } from "react";
import { Alert, Badge, Box, Button, CloseButton, Dialog, Field, HStack, Heading, Input, NativeSelect, Portal, Spinner, Stack, Table, Text } from "@chakra-ui/react";
import { LuUpload } from "react-icons/lu";
import { cancelImport, chooseImportCategories, chooseImportPeople, createCategory, getAllCategories, getCategoryGroups, matchImportColumns, uploadImport } from "../api/endpoints";
import { getToken } from "../lib/auth";
import { compareCategories } from "../lib/categoryName";
import { followImport, queueImport } from "../lib/importJobs";
import { formatMoney } from "../lib/locale";

const STEPS = [
    { id: "file", label: "Arquivo" },
    { id: "formats", label: "Formatos" },
    { id: "columns", label: "Colunas" },
    { id: "check", label: "Conferência" },
    { id: "categories", label: "Categorias" },
    { id: "people", label: "Pessoas" },
    { id: "confirm", label: "Confirmar" },
];
const FALLBACK_GROUP = "Outros";
const NEW_CATEGORY = "new"; // the value of the "create it" choice in a category's list

// The fields of a transaction, as the page's table of columns names them; the last two may be left out.
const FIELDS = [
    { name: "Data", required: true },
    { name: "Descrição", required: true },
    { name: "Categoria", required: true },
    { name: "Valor", required: true },
    { name: "Tipo", required: false, ifEmpty: "se vazio é Débito" },
    { name: "Pessoa", required: false, ifEmpty: "se vazio é quem está importando" },
];

// How the file writes dates and amounts, and what the sign of the amount means. "Automático" looks at the file.
const DATE_FORMATS = [
    { value: "auto", label: "Automático" },
    { value: "day_first", label: "DD/MM/AAAA (15/03/2026)" },
    { value: "month_first", label: "MM/DD/AAAA (03/15/2026)" },
    { value: "iso", label: "AAAA-MM-DD (2026-10-13)" },
];
const AMOUNT_FORMATS = [
    { value: "auto", label: "Automático" },
    { value: "br", label: "1.234,56 (vírgula nos centavos)" },
    { value: "us", label: "1,234.56 (ponto nos centavos)" },
];
const SIGNS = [
    { value: "type_column", label: "Sempre positivo; débito ou crédito vem na coluna Tipo" },
    { value: "negative_debit", label: "Negativo é débito, positivo é crédito" },
    { value: "negative_credit", label: "Positivo é débito, negativo é crédito" },
];
const DEFAULT_FORMATS = { dateOrder: "auto", amountStyle: "auto", sign: "type_column" };
const DATE_ORDER_NAMES = { day_first: "dia/mês/ano", month_first: "mês/dia/ano", iso: "ano-mês-dia" };

const columnLabel = (name, index) => (name ? name : `Coluna ${index + 1} (sem nome)`);

const fileDate = (iso) => iso.split("-").reverse().join("/"); // 2026-03-15 -> 15/03/2026, like the file

function StepIndicator({ current }) {
    return (
        <HStack as="ol" listStyleType="none" columnGap={5} rowGap={2} flexWrap="wrap" m={0} p={0} aria-label="Passos da importação">
            {STEPS.map((step, index) => (
                <HStack as="li" key={step.id} gap={2} aria-current={step.id === current ? "step" : undefined}>
                    <Badge colorPalette={step.id === current ? "blue" : "gray"} variant={step.id === current ? "solid" : "subtle"}>
                        {index + 1}
                    </Badge>
                    <Text fontSize="sm" fontWeight={step.id === current ? "semibold" : "normal"} color={step.id === current ? "fg" : "fg.muted"}>
                        {step.label}
                    </Text>
                </HStack>
            ))}
        </HStack>
    );
}

// A titled block of a step, so what belongs together is together: a title, a line saying what it is for, the content.
function Section({ title, hint, children }) {
    return (
        <Box as="section" borderWidth="1px" borderRadius="lg" p={{ base: 4, md: 5 }}>
            <Stack gap={4}>
                <Stack gap={1}>
                    <Heading as="h3" size="sm">{title}</Heading>
                    {hint && <Text fontSize="sm" color="fg.muted">{hint}</Text>}
                </Stack>
                {children}
            </Stack>
        </Box>
    );
}

// The positions of the columns in use. The Tipo column is not used when the sign of the amount says the direction.
function usedColumns(choice, formats) {
    return FIELDS.filter((field) => formats.sign === "type_column" || field.name !== "Tipo")
        .map((field) => choice[field.name])
        .filter((value) => value !== undefined && value !== "");
}

// What went wrong with the file or the chosen columns: the message and, when rows are wrong, all of them with their row.
function ProblemsAlert({ error }) {
    return (
        <Alert.Root status="error" role="alert">
            <Alert.Indicator />
            <Alert.Content>
                <Alert.Title>{error.detail}</Alert.Title>
                {error.problems.length > 0 && (
                    <Box mt={2} maxH="48" overflowY="auto" w="full">
                        <Table.Root size="sm" aria-label="Problemas encontrados">
                            <Table.Header>
                                <Table.Row>
                                    <Table.ColumnHeader>Linha</Table.ColumnHeader>
                                    <Table.ColumnHeader>O que está errado</Table.ColumnHeader>
                                </Table.Row>
                            </Table.Header>
                            <Table.Body>
                                {error.problems.map((problem, index) => (
                                    <Table.Row key={index}>
                                        <Table.Cell>{problem.row}</Table.Cell>
                                        <Table.Cell>{problem.message}</Table.Cell>
                                    </Table.Row>
                                ))}
                            </Table.Body>
                        </Table.Root>
                        {error.problemsTotal > error.problems.length && (
                            <Text fontSize="sm" mt={2}>
                                E mais {error.problemsTotal - error.problems.length} problemas. Corrija estes e envie de novo.
                            </Text>
                        )}
                    </Box>
                )}
            </Alert.Content>
        </Alert.Root>
    );
}

// Step 1: choose the file. The server checks all of it; a file with any wrong row is refused with the list of problems.
function FileStep({ file, setFile, checking, error }) {
    const input = useRef(null);
    return (
        <Stack gap={5}>
            <Section
                title="Planilha"
                hint="Escolha o arquivo (.xlsx ou .csv, até 5 MB). Em planilhas, fórmulas precisam ter sido calculadas e salvas no Excel. Nos próximos passos você diz como ele escreve datas e valores e qual coluna é qual, e conferimos o arquivo inteiro antes de salvar qualquer coisa."
            >
                <Field.Root invalid={!!error}>
                    <Field.Label>Arquivo</Field.Label>
                    <HStack gap={3} flexWrap="wrap">
                        <Button variant="outline" onClick={() => input.current?.click()} disabled={checking}>
                            <LuUpload /> Escolher arquivo
                        </Button>
                        <Text fontSize="sm" color="fg.muted">{file ? file.name : "Nenhum arquivo escolhido"}</Text>
                    </HStack>
                    {/* The real input stays in the page (hidden) so a screen reader and the tests can reach it by its label */}
                    <Input
                        ref={input}
                        type="file"
                        aria-label="Arquivo da planilha"
                        accept=".xlsx,.csv"
                        display="none"
                        onChange={(event) => setFile(event.target.files?.[0] ?? null)}
                    />
                </Field.Root>
            </Section>

            {error && <ProblemsAlert error={error} />}
        </Stack>
    );
}

function FormatSelect({ label, value, options, onChange }) {
    return (
        <Field.Root>
            <Field.Label>{label}</Field.Label>
            <NativeSelect.Root>
                <NativeSelect.Field value={value} onChange={(e) => onChange(e.target.value)}>
                    {options.map((option) => (
                        <option key={option.value} value={option.value}>{option.label}</option>
                    ))}
                </NativeSelect.Field>
                <NativeSelect.Indicator />
            </NativeSelect.Root>
        </Field.Root>
    );
}

// The first rows of the file, to recognise its columns and the way it writes dates and amounts.
function SampleTable({ job }) {
    return (
        <Box overflowX="auto">
            <Table.Root size="sm" aria-label="Primeiras linhas do arquivo">
                <Table.Header>
                    <Table.Row>
                        {job.columns.map((name, index) => (
                            <Table.ColumnHeader key={index}>{columnLabel(name, index)}</Table.ColumnHeader>
                        ))}
                    </Table.Row>
                </Table.Header>
                <Table.Body>
                    {job.sample.map((row, rowIndex) => (
                        <Table.Row key={rowIndex}>
                            {job.columns.map((_name, index) => (
                                <Table.Cell key={index}>{row[index] ?? ""}</Table.Cell>
                            ))}
                        </Table.Row>
                    ))}
                </Table.Body>
            </Table.Root>
        </Box>
    );
}

const SAMPLE_TITLE = "Primeiras linhas do arquivo";
const SAMPLE_HINT = "Use estas linhas para reconhecer as colunas e o jeito de escrever datas e valores.";

// Step 2: how the file writes dates and amounts, and what the sign of the amount means; each row is then checked that way.
function FormatsStep({ job, formats, setFormats }) {
    return (
        <Stack gap={5}>
            <Section
                title="Como o arquivo escreve os valores"
                hint="Conferimos cada linha pelo formato que você escolher. No automático, olhamos o arquivo todo; uma data como 05/03/2026, que pode ser dos dois jeitos, é lida como dia/mês/ano, o formato do arquivo que o app exporta."
            >
                <Box display="grid" gridTemplateColumns={{ base: "1fr", md: "repeat(3, 1fr)" }} gap={5}>
                    <FormatSelect label="Formato das datas" value={formats.dateOrder} options={DATE_FORMATS} onChange={(dateOrder) => setFormats((c) => ({ ...c, dateOrder }))} />
                    <FormatSelect label="Formato dos valores" value={formats.amountStyle} options={AMOUNT_FORMATS} onChange={(amountStyle) => setFormats((c) => ({ ...c, amountStyle }))} />
                    <FormatSelect label="Sinal do valor" value={formats.sign} options={SIGNS} onChange={(sign) => setFormats((c) => ({ ...c, sign }))} />
                </Box>
            </Section>

            <Section title={SAMPLE_TITLE} hint={SAMPLE_HINT}>
                <SampleTable job={job} />
            </Section>
        </Stack>
    );
}

// Step 3: which column of the file is which field. What has the same name as the field is already chosen.
function ColumnsStep({ job, choice, setChoice, formats }) {
    const taken = usedColumns(choice, formats);
    const repeated = taken.length !== new Set(taken).size;
    const byType = formats.sign === "type_column"; // otherwise the sign of the amount says it and there is no Tipo column
    const fields = FIELDS.filter((field) => byType || field.name !== "Tipo");
    const fieldSelect = (field) => (
        <Field.Root key={field.name} required={field.required}>
            <Field.Label>{field.required ? field.name : `${field.name} (opcional, ${field.ifEmpty})`}</Field.Label>
            <NativeSelect.Root>
                <NativeSelect.Field
                    aria-label={`Coluna para ${field.name}`}
                    value={choice[field.name]}
                    onChange={(e) => setChoice((current) => ({ ...current, [field.name]: e.target.value }))}
                >
                    <option value="">{field.required ? "Escolha..." : "Não usar"}</option>
                    {job.columns.map((name, index) => (
                        <option key={index} value={String(index)}>{columnLabel(name, index)}</option>
                    ))}
                </NativeSelect.Field>
                <NativeSelect.Indicator />
            </NativeSelect.Root>
        </Field.Root>
    );
    const grid = { display: "grid", gridTemplateColumns: { base: "1fr", md: "repeat(2, 1fr)" }, gap: 5 };
    return (
        <Stack gap={5}>
            <Section
                title="Campos obrigatórios"
                hint="Diga qual coluna do arquivo é cada informação da transação. Depois conferimos todas as linhas; se alguma tiver problema, nada é importado."
            >
                <Box {...grid}>{fields.filter((field) => field.required).map(fieldSelect)}</Box>
                {repeated && <Text color="fg.error" role="alert">Uma mesma coluna não pode ser usada para dois campos.</Text>}
            </Section>

            {fields.some((field) => !field.required) && (
                <Section title="Campos opcionais" hint="Sem Tipo, tudo entra como débito. Sem Pessoa, as transações ficam com quem está importando.">
                    <Box {...grid}>{fields.filter((field) => !field.required).map(fieldSelect)}</Box>
                </Section>
            )}

            <Section title={SAMPLE_TITLE} hint={SAMPLE_HINT}>
                <SampleTable job={job} />
            </Section>
        </Stack>
    );
}

// How the file was read, for the person to notice a wrong guess.
function HowRead({ job }) {
    if (!job.date_order) return null;
    return (
        <Text fontSize="sm" color="fg.muted">
            Datas lidas como {DATE_ORDER_NAMES[job.date_order]}
            {job.sign && job.sign !== "type_column" ? "; o sinal do valor diz se é débito ou crédito" : ""}. Se não for
            isso, volte e escolha o formato.
        </Text>
    );
}

// Step 4: every row of the file is checked the way steps 2 and 3 said. All the problems are listed, or all is well.
function CheckStep({ job, running, error }) {
    return (
        <Stack gap={5}>
            <Section title="Resultado da conferência" hint="Cada linha do arquivo é conferida pelos formatos e colunas que você escolheu.">
                {running && (
                    <HStack>
                        <Spinner size="sm" />
                        <Text>Conferindo todas as linhas do arquivo...</Text>
                    </HStack>
                )}
                {error && (
                    <>
                        <ProblemsAlert error={error} />
                        <Text fontSize="sm" color="fg.muted">
                            Nada foi importado. Corrija o arquivo e envie de novo, ou volte e mude as colunas ou os formatos,
                            se o problema for o jeito de ler o arquivo.
                        </Text>
                    </>
                )}
                {!running && !error && job.total_rows !== null && job.total_rows !== undefined && (
                    <Stack gap={3}>
                        <Alert.Root status="success">
                            <Alert.Indicator />
                            <Alert.Title>
                                Tudo certo: {job.total_rows === 1 ? "a linha do arquivo foi conferida" : `as ${job.total_rows} linhas do arquivo foram conferidas`}.
                            </Alert.Title>
                        </Alert.Root>
                        <HowRead job={job} />
                    </Stack>
                )}
            </Section>
        </Stack>
    );
}

// One category of the file that the family does not have: use one it has, or create it.
function CategoryRow({ item, row, onChange, categories, groups, onCreate }) {
    const [creating, setCreating] = useState(false);
    const [error, setError] = useState("");
    const byGroup = groups.map((group) => ({
        group,
        items: categories.filter((category) => category.group_id === group.id).sort(compareCategories),
    }));

    const create = async () => {
        const name = row.newName.trim();
        if (!name) {
            setError("O nome da categoria não pode ficar vazio.");
            return;
        }
        setCreating(true);
        const result = await createCategory({ name, group_id: Number(row.groupId) }, getToken());
        setCreating(false);
        if (result.ok) {
            setError("");
            await onCreate(item.name, result.data.id);
        } else if (result.status === 409 || result.status === 422) {
            setError(result.detail); // for example that the name already exists: then it can be chosen from the list
        } else {
            setError("Não foi possível criar a categoria. Tente novamente.");
        }
    };

    return (
        <Stack as="li" gap={4} borderWidth="1px" borderRadius="md" p={4} listStyleType="none">
            <Text>
                <Text as="span" fontWeight="semibold">{item.name}</Text>
                <Text as="span" color="fg.muted"> · {item.rows === 1 ? "1 linha" : `${item.rows} linhas`}</Text>
            </Text>
            <Field.Root>
                <Field.Label>{`Categoria para "${item.name}"`}</Field.Label>
                <NativeSelect.Root>
                    <NativeSelect.Field value={row.value} onChange={(e) => onChange({ value: e.target.value })}>
                        <option value="">Escolha...</option>
                        <option value={NEW_CATEGORY}>Criar uma categoria nova</option>
                        {byGroup.map(({ group, items }) =>
                            items.length > 0 ? (
                                <optgroup key={group.id} label={group.name}>
                                    {items.map((category) => (
                                        <option key={category.id} value={String(category.id)}>{category.name}</option>
                                    ))}
                                </optgroup>
                            ) : null,
                        )}
                    </NativeSelect.Field>
                    <NativeSelect.Indicator />
                </NativeSelect.Root>
            </Field.Root>

            {row.value === NEW_CATEGORY && (
                <Stack gap={3} borderStartWidth="2px" ps={3}>
                    <Field.Root invalid={!!error}>
                        <Field.Label>Nome da nova categoria</Field.Label>
                        <Input value={row.newName} onChange={(e) => { onChange({ newName: e.target.value }); setError(""); }} maxLength={100} />
                        <Field.ErrorText>{error}</Field.ErrorText>
                    </Field.Root>
                    <Field.Root>
                        <Field.Label>Grupo da nova categoria</Field.Label>
                        <NativeSelect.Root>
                            <NativeSelect.Field value={row.groupId} onChange={(e) => onChange({ groupId: e.target.value })}>
                                {groups.map((group) => (
                                    <option key={group.id} value={group.id}>{group.name}</option>
                                ))}
                            </NativeSelect.Field>
                            <NativeSelect.Indicator />
                        </NativeSelect.Root>
                    </Field.Root>
                    <Button alignSelf="start" size="sm" onClick={create} loading={creating}>Criar categoria</Button>
                </Stack>
            )}
        </Stack>
    );
}

// Step 4: for each category of the file the family does not have yet, use an existing one or create it.
function CategoriesStep({ unknown, rows, setRows, categories, groups, reloadCategories, error }) {
    const update = (name, changes) => setRows((current) => ({ ...current, [name]: { ...current[name], ...changes } }));
    const created = async (name, id) => {
        await reloadCategories();
        update(name, { value: String(id) }); // the new category is now one of the ones to choose from
    };

    return (
        <Stack gap={5}>
            <Section
                title="Categorias que você ainda não tem"
                hint={`O arquivo usa ${unknown.length === 1 ? "uma categoria que você ainda não tem" : `${unknown.length} categorias que você ainda não tem`}. Para cada uma, escolha uma categoria que já existe ou crie uma nova. Nada é salvo até o último passo.`}
            >
                <Stack as="ul" gap={4} m={0} p={0} aria-label="Categorias do arquivo que não existem">
                    {unknown.map((item) => (
                        <CategoryRow
                            key={item.name}
                            item={item}
                            row={rows[item.name]}
                            onChange={(changes) => update(item.name, changes)}
                            categories={categories}
                            groups={groups}
                            onCreate={created}
                        />
                    ))}
                </Stack>
                {error && <Text color="fg.error" role="alert">{error}</Text>}
            </Section>
        </Stack>
    );
}

// Step 6: every name of the Pessoa column and the member it stands for. The ones that match a member's name come
// already chosen, and any of them can be changed; the others have to be chosen.
function PeopleStep({ people, members, choices, setChoices, error }) {
    const unmatched = people.filter((item) => item.user_id == null).length;
    return (
        <Stack gap={5}>
            <Section
                title="Pessoas do arquivo"
                hint={`Cada nome da coluna Pessoa precisa de um membro da família. Os que têm o mesmo nome de alguém já vêm escolhidos, mas você pode trocar.${unmatched > 0 ? ` ${unmatched === 1 ? "Um nome" : `${unmatched} nomes`} sem correspondência: escolha a quem pertence.` : ""} Nada é salvo até o último passo.`}
            >
                <Stack as="ul" gap={4} m={0} p={0} aria-label="Pessoas do arquivo">
                    {people.map((item) => (
                        <Field.Root as="li" key={item.name}>
                            <Field.Label>
                                &ldquo;{item.name}&rdquo; ({item.rows === 1 ? "1 linha" : `${item.rows} linhas`})
                                <Badge colorPalette={item.user_id == null ? "orange" : "green"} variant="subtle">
                                    {item.user_id == null ? "Sem correspondência" : "Reconhecido pelo nome"}
                                </Badge>
                            </Field.Label>
                            <NativeSelect.Root>
                                <NativeSelect.Field
                                    aria-label={`Pessoa para ${item.name}`}
                                    value={choices[item.name] ?? ""}
                                    onChange={(e) => setChoices((current) => ({ ...current, [item.name]: e.target.value }))}
                                >
                                    <option value="">Escolha...</option>
                                    {members.map((member) => (
                                        <option key={member.id} value={String(member.id)}>{member.name}</option>
                                    ))}
                                </NativeSelect.Field>
                                <NativeSelect.Indicator />
                            </NativeSelect.Root>
                        </Field.Root>
                    ))}
                </Stack>
                {error && <Text color="fg.error" role="alert">{error}</Text>}
            </Section>
        </Stack>
    );
}

// Step 5: what is about to happen, before it does.
function ConfirmStep({ job }) {
    const hidden = job.skipped_count - job.skipped.length;
    return (
        <Stack gap={5}>
            <Section title="Resumo">
                <Text>
                    <Text as="span" fontWeight="semibold">{job.to_import === 1 ? "1 transação será importada" : `${job.to_import} transações serão importadas`}</Text>
                    {job.skipped_count > 0 && (
                        <Text as="span">
                            {" "}e {job.skipped_count === 1 ? "1 será ignorada porque já existe" : `${job.skipped_count} serão ignoradas porque já existem`}
                        </Text>
                    )}
                    .
                </Text>
                {job.to_import === 0 && <Text color="fg.muted">Todas as transações do arquivo já existem. Não há nada para importar.</Text>}
                <HowRead job={job} />
                <Text fontSize="sm" color="fg.muted">
                    A importação roda em segundo plano: você pode continuar usando o app e avisamos quando terminar.
                </Text>
            </Section>

            {job.skipped_count > 0 && (
                <Section title="Já existem e serão ignoradas" hint="Mesmo dia, descrição, valor, categoria e tipo de uma transação que você já tem.">
                    <Box maxH="48" overflowY="auto">
                        <Table.Root size="sm" aria-label="Transações que serão ignoradas">
                            <Table.Header>
                                <Table.Row>
                                    <Table.ColumnHeader>Linha</Table.ColumnHeader>
                                    <Table.ColumnHeader>Data</Table.ColumnHeader>
                                    <Table.ColumnHeader>Descrição</Table.ColumnHeader>
                                    <Table.ColumnHeader textAlign="end">Valor</Table.ColumnHeader>
                                </Table.Row>
                            </Table.Header>
                            <Table.Body>
                                {job.skipped.map((row) => (
                                    <Table.Row key={row.row}>
                                        <Table.Cell>{row.row}</Table.Cell>
                                        <Table.Cell>{fileDate(row.date)}</Table.Cell>
                                        <Table.Cell>{row.label}</Table.Cell>
                                        <Table.Cell textAlign="end">{formatMoney(row.value / 100)}</Table.Cell>
                                    </Table.Row>
                                ))}
                            </Table.Body>
                        </Table.Root>
                    </Box>
                    {hidden > 0 && <Text fontSize="sm" color="fg.muted">E mais {hidden}.</Text>}
                </Section>
            )}
        </Stack>
    );
}

/** The import in steps: choose the file, settle the categories it mentions, confirm. */
export default function ImportDialog({ open, onClose }) {
    const [step, setStep] = useState("file");
    const [file, setFile] = useState(null);
    const [checking, setChecking] = useState(false);
    const [fileError, setFileError] = useState(null);
    const [job, setJob] = useState(null); // the file, kept by the server until it is imported or given up
    const [choice, setChoice] = useState({}); // the column chosen for each field ("" for none; the position otherwise)
    const [formats, setFormats] = useState(DEFAULT_FORMATS);
    const [checked, setChecked] = useState(false); // every row was checked and is fine
    const [checkError, setCheckError] = useState(null);
    const [unknown, setUnknown] = useState([]); // the categories of the file to settle (fixed when the step opens)
    const [rows, setRows] = useState({}); // what was chosen for each of them
    const [categories, setCategories] = useState([]);
    const [groups, setGroups] = useState([]);
    const [categoryError, setCategoryError] = useState("");
    const [filePeople, setFilePeople] = useState([]); // the names of the Pessoa column, with the member each was matched to
    const [peopleChoices, setPeopleChoices] = useState({}); // the member chosen for each ("" while not chosen)
    const [peopleError, setPeopleError] = useState("");
    const [busy, setBusy] = useState(false);

    // Start from the first step every time the dialog opens
    useEffect(() => {
        if (open) {
            setStep("file");
            setFile(null);
            setFileError(null);
            setJob(null);
            setChoice({});
            setFormats(DEFAULT_FORMATS);
            setCheckError(null);
            setChecked(false);
            setUnknown([]);
            setRows({});
            setCategoryError("");
        }
    }, [open]);

    const loadCategories = async () => {
        const token = getToken();
        const [list, groupList] = await Promise.all([getAllCategories(token), getCategoryGroups(token)]);
        if (list?.data) setCategories(list.data);
        if (groupList?.ok) setGroups(groupList.data);
        return groupList?.ok ? groupList.data : [];
    };

    // Throw the checked file away (best effort) and close
    const close = () => {
        if (job) cancelImport(job.id, getToken());
        onClose();
    };

    const handleUpload = async () => {
        setChecking(true);
        setFileError(null);
        const result = await uploadImport(file, getToken());
        setChecking(false);
        if (!result.ok) {
            setFileError({
                detail: result.detail || "Não foi possível enviar o arquivo. Tente novamente.",
                problems: result.problems ?? [],
                problemsTotal: result.problemsTotal ?? 0,
            });
            return;
        }
        setJob(result.data);
        // Start from what the server recognised by name
        setChoice(Object.fromEntries(FIELDS.map((field) => [field.name, String(result.data.suggested_map[field.name] ?? "")])));
        setFormats({ ...DEFAULT_FORMATS, sign: result.data.suggested_sign ?? "type_column" });
        setCheckError(null);
        setStep("formats");
    };

    // After the categories: to the names of the Pessoa column that matched nobody, or to confirming
    const toPeopleOrConfirm = (current) => {
        const people = current.people ?? [];
        setFilePeople(people);
        // What the server matched by itself is already chosen, and can be changed; the others wait for a choice
        setPeopleChoices(Object.fromEntries(people.map((item) => [item.name, item.user_id == null ? "" : String(item.user_id)])));
        setPeopleError("");
        setStep(people.length > 0 ? "people" : "confirm");
    };

    // Move on once the columns are matched and every row is fine: to the categories the file needs, or to confirming
    const goOn = async (checked) => {
        setJob(checked);
        if (checked.unknown_categories.length === 0) {
            setUnknown([]);
            toPeopleOrConfirm(checked);
            return;
        }
        const groupList = await loadCategories();
        const fallback = groupList.find((group) => group.name === FALLBACK_GROUP) ?? groupList[0];
        setUnknown(checked.unknown_categories);
        setRows(
            Object.fromEntries(
                checked.unknown_categories.map((item) => [item.name, { value: "", newName: item.name, groupId: String(fallback?.id ?? "") }]),
            ),
        );
        setCategoryError("");
        setStep("categories");
    };

    // Step 3 -> 4: check every row the way the person said. The result is shown in step 4.
    const runCheck = async () => {
        setStep("check");
        setBusy(true);
        setCheckError(null);
        setChecked(false);
        const byType = formats.sign === "type_column";
        const mapping = Object.fromEntries(
            FIELDS.map((field) => [field.name, !byType && field.name === "Tipo" ? null : choice[field.name] === "" ? null : Number(choice[field.name])]),
        );
        const result = await matchImportColumns(job.id, mapping, formats, getToken());
        if (result.ok) {
            setJob({ ...job, ...result.data });
            setChecked(true);
        } else {
            setCheckError({
                detail: result.detail || "Não foi possível conferir o arquivo. Tente novamente.",
                problems: result.problems ?? [],
                problemsTotal: result.problemsTotal ?? 0,
            });
        }
        setBusy(false);
    };

    // Step 4 -> 5 (or straight to confirming when the file needs no new category)
    const handleChecked = async () => {
        setBusy(true);
        await goOn(job);
        setBusy(false);
    };

    const handleChosen = async () => {
        setBusy(true);
        setCategoryError("");
        const mapping = Object.fromEntries(unknown.map((item) => [item.name, Number(rows[item.name].value)]));
        const result = await chooseImportCategories(job.id, mapping, getToken());
        setBusy(false);
        if (!result.ok) {
            setCategoryError(result.detail || "Não foi possível salvar suas escolhas. Tente novamente.");
            return;
        }
        const merged = { ...job, ...result.data }; // keeps the sample of the file, for going back to the columns
        setJob(merged);
        toPeopleOrConfirm(merged);
    };

    const handlePeopleChosen = async () => {
        setBusy(true);
        setPeopleError("");
        const mapping = Object.fromEntries(filePeople.map((item) => [item.name, Number(peopleChoices[item.name])]));
        const result = await chooseImportPeople(job.id, mapping, getToken());
        setBusy(false);
        if (!result.ok) {
            setPeopleError(result.detail || "Não foi possível salvar suas escolhas. Tente novamente.");
            return;
        }
        setJob({ ...job, ...result.data });
        setStep("confirm");
    };

    // One step back: the file stays on the server until another one is sent, so the choices are not lost
    const BACK = { formats: "file", columns: "formats", check: "columns", categories: "check", people: unknown.length > 0 ? "categories" : "check" };
    const goBack = () => {
        if (step === "check") {
            setChecked(false);
            setCheckError(null);
        }
        setStep(step === "confirm" ? (filePeople.length > 0 ? "people" : unknown.length > 0 ? "categories" : "check") : BACK[step]);
    };

    const handleStart = async () => {
        setBusy(true);
        const queued = await queueImport(job.id);
        setBusy(false);
        if (!queued) return;
        setJob(null); // it is the server's now: closing must not throw it away
        onClose();
        followImport(queued); // not awaited: the result is announced even if the user goes elsewhere
    };

    const taken = usedColumns(choice, formats);
    const columnsReady = job && FIELDS.filter((f) => f.required).every((f) => choice[f.name] !== "" && choice[f.name] !== undefined) && taken.length === new Set(taken).size;
    const allPeopleChosen = filePeople.length > 0 && filePeople.every((item) => /^\d+$/.test(peopleChoices[item.name] ?? ""));
    const allChosen = unknown.length > 0 && unknown.every((item) => /^\d+$/.test(rows[item.name]?.value ?? ""));

    return (
        <Dialog.Root
            open={open}
            onOpenChange={(e) => !e.open && !busy && !checking && close()}
            size="xl"
            scrollBehavior="inside"
            closeOnInteractOutside={false}
        >
            <Portal>
                <Dialog.Backdrop />
                <Dialog.Positioner>
                    <Dialog.Content maxW="5xl">
                        <Dialog.Header px={{ base: 4, md: 8 }} pt={{ base: 5, md: 7 }} pb={4}>
                            <Stack gap={4}>
                                <Dialog.Title>Importar transações</Dialog.Title>
                                <StepIndicator current={step} />
                            </Stack>
                        </Dialog.Header>
                        <Dialog.Body px={{ base: 4, md: 8 }} py={5}>
                            {step === "file" && <FileStep file={file} setFile={setFile} checking={checking} error={fileError} />}
                            {step === "formats" && job && <FormatsStep job={job} formats={formats} setFormats={setFormats} />}
                            {step === "columns" && job && <ColumnsStep job={job} choice={choice} setChoice={setChoice} formats={formats} />}
                            {step === "check" && job && <CheckStep job={job} running={busy && !checked} error={checkError} />}
                            {step === "categories" && (
                                <CategoriesStep
                                    unknown={unknown}
                                    rows={rows}
                                    setRows={setRows}
                                    categories={categories}
                                    groups={groups}
                                    reloadCategories={loadCategories}
                                    error={categoryError}
                                />
                            )}
                            {step === "people" && job && (
                                <PeopleStep
                                    people={filePeople}
                                    members={job.members ?? []}
                                    choices={peopleChoices}
                                    setChoices={setPeopleChoices}
                                    error={peopleError}
                                />
                            )}
                            {step === "confirm" && job && <ConfirmStep job={job} />}
                            {checking && <Spinner mt={4} aria-label="Conferindo o arquivo" />}
                        </Dialog.Body>
                        <Dialog.Footer px={{ base: 4, md: 8 }} py={5} gap={3} borderTopWidth="1px">
                            <Button variant="outline" onClick={close} disabled={busy || checking}>Cancelar</Button>
                            {step !== "file" && (
                                <Button variant="outline" onClick={goBack} disabled={busy}>Voltar</Button>
                            )}
                            {step === "file" && (
                                <Button onClick={handleUpload} disabled={!file} loading={checking}>Enviar arquivo</Button>
                            )}
                            {step === "formats" && <Button onClick={() => setStep("columns")}>Próximo</Button>}
                            {step === "columns" && (
                                <Button onClick={runCheck} disabled={!columnsReady}>Próximo</Button>
                            )}
                            {step === "check" && (
                                <Button onClick={handleChecked} disabled={!checked || busy}>Próximo</Button>
                            )}
                            {step === "categories" && (
                                <Button onClick={handleChosen} disabled={!allChosen} loading={busy}>Próximo</Button>
                            )}
                            {step === "people" && (
                                <Button onClick={handlePeopleChosen} disabled={!allPeopleChosen} loading={busy}>Próximo</Button>
                            )}
                            {step === "confirm" && (
                                <Button onClick={handleStart} disabled={!job || job.to_import === 0} loading={busy}>Importar</Button>
                            )}
                        </Dialog.Footer>
                        <Dialog.CloseTrigger asChild>
                            <CloseButton size="sm" />
                        </Dialog.CloseTrigger>
                    </Dialog.Content>
                </Dialog.Positioner>
            </Portal>
        </Dialog.Root>
    );
}
