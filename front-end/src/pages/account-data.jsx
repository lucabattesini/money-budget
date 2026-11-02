import { Heading, Separator, Stack, Text } from "@chakra-ui/react";

// Placeholder: the bulk import and the export (Excel / CSV) will both live on this page.
export default function AccountData() {
    return (
        <Stack gap={6} maxW="lg">
            <Stack gap={1}>
                <Heading size="xl">Importar e exportar</Heading>
                <Text color="fg.muted">Leve suas transações para outro lugar, ou traga-as de uma planilha.</Text>
            </Stack>

            <Stack gap={2}>
                <Heading size="md">Importar</Heading>
                <Text color="fg.muted">Em breve: envie uma planilha Excel ou CSV para cadastrar várias transações de uma vez.</Text>
            </Stack>

            <Separator />

            <Stack gap={2}>
                <Heading size="md">Exportar</Heading>
                <Text color="fg.muted">Em breve: baixe suas transações em Excel ou CSV.</Text>
            </Stack>
        </Stack>
    );
}
