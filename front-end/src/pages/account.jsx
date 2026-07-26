import { useState, useEffect } from "react";
import {
    Center,
    Stack,
    Heading,
    Text,
    Input,
    Button,
    Box,
    Separator,
    Badge,
    Avatar,
    Field,
    Spinner,
} from "@chakra-ui/react";
import { FcGoogle } from "react-icons/fc";
import { MdOutlineWhatsapp } from "react-icons/md";
import { getMe, updatePhone } from "../api/endpoints";
import { getToken, removeToken } from "../lib/auth";

export default function Account() {
    const [user, setUser] = useState(null);
    const [whatsappPhone, setWhatsappPhone] = useState("");
    const [saved, setSaved] = useState(false);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const token = getToken();
        if (token) {
            getMe(token).then((data) => {
                if (data && data.data) {
                    setUser(data.data);
                    setWhatsappPhone(data.data.whatsapp_phone || "");
                }
                setLoading(false);
            });
        } else {
            setLoading(false);
        }
    }, []);

    const handleSavePhone = async () => {
        const token = getToken();
        if (token) {
            const result = await updatePhone(whatsappPhone, token);
            if (result) {
                setSaved(true);
                setTimeout(() => setSaved(false), 2500);
            }
        }
    };

    const handleLogout = () => {
        removeToken();
        window.location.href = "/";
    };

    return (
        <Center minH="100vh">
            <Stack
                gap={8}
                w="full"
                maxW="sm"
                px={6}
                pt={16}
                pb={12}
            >
                {/* Header */}
                <Stack gap={1}>
                    <Heading size="2xl">Minha Conta</Heading>
                    <Text color="fg.muted">Gerencie seu perfil e integrações</Text>
                </Stack>

                {/* Profile card */}
                {loading ? (
                    <Center p={10}>
                        <Spinner size="xl" />
                    </Center>
                ) : user ? (
                    <Stack
                        gap={4}
                        p={5}
                        borderWidth="1px"
                        borderRadius="xl"
                    >
                        <Stack direction="row" align="center" gap={4}>
                            <Avatar.Root size="lg">
                                <Avatar.Fallback name={user.name} />
                                {user.picture && <Avatar.Image src={user.picture} />}
                            </Avatar.Root>
                            <Stack gap={0}>
                                <Text fontWeight="semibold">{user.name}</Text>
                                <Text fontSize="sm" color="fg.muted">{user.email}</Text>
                            </Stack>
                            <Badge
                                ml="auto"
                                colorPalette="green"
                                variant="subtle"
                                size="sm"
                                gap={1}
                            >
                                <FcGoogle />
                                Google
                            </Badge>
                        </Stack>
                    </Stack>
                ) : null}

                <Separator />

                {/* WhatsApp integration */}
                <Stack gap={4}>
                    <Stack gap={1}>
                        <Stack direction="row" align="center" gap={2}>
                            <MdOutlineWhatsapp size={20} color="#25D366" />
                            <Heading size="md">Integração com WhatsApp</Heading>
                        </Stack>
                        <Text fontSize="sm" color="fg.muted">
                            Vincule seu número para registrar despesas enviando uma mensagem.
                        </Text>
                    </Stack>

                    <Field.Root>
                        <Field.Label>Número de telefone</Field.Label>
                        <Input
                            id="whatsapp-phone-input"
                            placeholder="+55 51 99999-9999"
                            value={whatsappPhone}
                            onChange={(e) => setWhatsappPhone(e.target.value)}
                        />
                        <Field.HelperText>Inclua o código do país (ex: +55)</Field.HelperText>
                    </Field.Root>

                    <Button
                        id="save-whatsapp-btn"
                        onClick={handleSavePhone}
                        colorPalette={saved ? "green" : "gray"}
                        variant="outline"
                        w="full"
                    >
                        {saved ? "Salvo!" : "Salvar número"}
                    </Button>
                </Stack>

                <Separator />

                {/* Danger zone */}
                <Stack gap={3}>
                    <Text fontSize="sm" fontWeight="semibold" color="fg.muted">
                        Sessão
                    </Text>
                    <Button
                        id="logout-btn"
                        onClick={handleLogout}
                        variant="outline"
                        colorPalette="red"
                        w="full"
                    >
                        Sair
                    </Button>
                </Stack>
            </Stack>
        </Center>
    );
}
