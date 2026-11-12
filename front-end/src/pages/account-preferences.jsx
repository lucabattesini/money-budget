import { useEffect, useState } from "react";
import { Field, Heading, NativeSelect, Spinner, Stack, Switch, Text } from "@chakra-ui/react";
import { getFamily, updateFamilySettings } from "../api/endpoints";
import { getToken } from "../lib/auth";
import { CURRENCIES, LANGUAGES, TIMEZONES, setLocale, useLocale } from "../lib/locale";
import customToaster from "../utils/customToaster";
import PageHeading from "../components/PageHeading";

// The currency, the language and the timezone of the family. They apply to everyone in it, and any member can change them.
export default function AccountPreferences() {
    const { currency, language, timezone, merchantsEnabled } = useLocale();
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
        const before = { currency, language, timezone, merchants_enabled: merchantsEnabled };
        setLocale({ [field]: value });
        setSaving(true);
        const result = await updateFamilySettings({ [field]: value }, getToken());
        setSaving(false);
        if (!result.ok) {
            setLocale({ [field]: before[field] }); // only the field that failed: another change may have succeeded meanwhile
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
            <PageHeading title="Preferências">
                Valem para toda a família: todos veem os valores e as datas no mesmo formato, e o assistente do
                WhatsApp responde no idioma escolhido.
            </PageHeading>

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

            <Field.Root maxW="sm" disabled={saving}>
                <Field.Label>Fuso horário</Field.Label>
                <NativeSelect.Root>
                    <NativeSelect.Field value={timezone} onChange={(e) => change("timezone", e.target.value)}>
                        {TIMEZONES.map((option) => (
                            <option key={option.code} value={option.code}>{option.label}</option>
                        ))}
                    </NativeSelect.Field>
                    <NativeSelect.Indicator />
                </NativeSelect.Root>
                <Field.HelperText>
                    Decide qual é o dia e o mês de "agora": uma compra feita à noite fica no dia certo, mesmo em outro fuso.
                </Field.HelperText>
            </Field.Root>

            <Field.Root maxW="sm" disabled={saving}>
                <Switch.Root checked={merchantsEnabled} onCheckedChange={(e) => change("merchants_enabled", e.checked)}>
                    <Switch.HiddenInput />
                    <Switch.Control>
                        <Switch.Thumb />
                    </Switch.Control>
                    <Switch.Label>Estabelecimentos</Switch.Label>
                </Switch.Root>
                <Field.HelperText>
                    Liga um campo "Estabelecimento" nas transações (Uber, iFood, Netflix...), para ver quanto vai para cada
                    um. Desligar só esconde: nada é apagado.
                </Field.HelperText>
            </Field.Root>
        </Stack>
    );
}
