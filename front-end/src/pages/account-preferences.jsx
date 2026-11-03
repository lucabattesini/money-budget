import { useEffect, useState } from "react";
import { Field, Heading, NativeSelect, Spinner, Stack, Text } from "@chakra-ui/react";
import { getFamily, updateFamilySettings } from "../api/endpoints";
import { getToken } from "../lib/auth";
import { CURRENCIES, LANGUAGES, setLocale, useLocale } from "../lib/locale";
import customToaster from "../utils/customToaster";

// The currency and the language of the family. They apply to everyone in it, and any member can change them.
export default function AccountPreferences() {
    const { currency, language } = useLocale();
    const [loading, setLoading] = useState(true);
    const [failed, setFailed] = useState(false);
    const [saving, setSaving] = useState(false);

    useEffect(() => {
        const token = getToken();
        if (!token) {
            setLoading(false);
            return;
        }
        getFamily(token).then((result) => {
            if (result.ok) setLocale(result.data);
            else setFailed(true);
            setLoading(false);
        });
    }, []);

    // Saved as soon as it is chosen; the page shows the new format straight away and goes back if the save fails
    const change = async (field, value) => {
        const before = { currency, language };
        setLocale({ [field]: value });
        setSaving(true);
        const result = await updateFamilySettings({ [field]: value }, getToken());
        setSaving(false);
        if (!result.ok) {
            setLocale(before);
            customToaster("Erro", "error", result.detail || "Não foi possível salvar. Tente novamente.");
            return;
        }
        setLocale(result.data);
        customToaster("Pronto", "success", "Preferência salva para toda a família.");
    };

    if (loading) return <Spinner size="xl" />;
    if (failed) return <Text color="fg.error">Não foi possível carregar as preferências. Tente novamente mais tarde.</Text>;

    return (
        <Stack gap={8} maxW="3xl">
            <Stack gap={1}>
                <Heading size="xl">Preferências</Heading>
                <Text color="fg.muted">
                    Valem para toda a família: todos veem os valores e as datas no mesmo formato, e o assistente do
                    WhatsApp responde no idioma escolhido.
                </Text>
            </Stack>

            <Field.Root maxW="sm" disabled={saving}>
                <Field.Label>Moeda</Field.Label>
                <NativeSelect.Root>
                    <NativeSelect.Field value={currency} onChange={(e) => change("currency", e.target.value)}>
                        {CURRENCIES.map((option) => (
                            <option key={option.code} value={option.code}>{option.label}</option>
                        ))}
                    </NativeSelect.Field>
                    <NativeSelect.Indicator />
                </NativeSelect.Root>
                <Field.HelperText>Só muda como os valores são mostrados: nada é convertido.</Field.HelperText>
            </Field.Root>

            <Field.Root maxW="sm" disabled={saving}>
                <Field.Label>Idioma</Field.Label>
                <NativeSelect.Root>
                    <NativeSelect.Field value={language} onChange={(e) => change("language", e.target.value)}>
                        {LANGUAGES.map((option) => (
                            <option key={option.code} value={option.code}>{option.label}</option>
                        ))}
                    </NativeSelect.Field>
                    <NativeSelect.Indicator />
                </NativeSelect.Root>
                <Field.HelperText>
                    Define o formato de números e datas e o idioma das respostas do assistente. O texto das telas continua em português por enquanto.
                </Field.HelperText>
            </Field.Root>
        </Stack>
    );
}
