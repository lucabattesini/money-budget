import { GoogleLogin } from "@react-oauth/google";
import { Center, Stack, Heading, Text, Box, Alert } from "@chakra-ui/react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { loginWithGoogle } from "../api/endpoints";
import { saveToken } from "../lib/auth";

const hasClientId = Boolean(import.meta.env.VITE_GOOGLE_CLIENT_ID);

function LoginGoogleForm() {
    const navigate = useNavigate();
    const [searchParams] = useSearchParams();
    const phone = searchParams.get("phone");

    const onSuccess = async (credentialResponse) => {
        // credentialResponse.credential is the id_token
        const data = await loginWithGoogle(credentialResponse.credential, phone);
        if (data?.data?.token) {
            saveToken(data.data.token);
            navigate("/");
        }
    };

    const onError = () => {
        console.error("Google login failed");
    };

    return (
        <Center>
            <GoogleLogin
                onSuccess={onSuccess}
                onError={onError}
                size="large"
            />
        </Center>
    );
}

export default function LoginGoogle() {
    return (
        <Center minH="100vh">
            <Stack gap={8} align="center" maxW="sm" w="full" px={6}>
                <Stack gap={2} align="center" textAlign="center">
                    <Heading size="2xl">Bem-vindo de volta!</Heading>
                    <Text color="fg.muted">Faça login na sua conta para continuar</Text>
                </Stack>

                <Box w="full">
                    {!hasClientId ? (
                        <Alert.Root status="warning" borderRadius="lg">
                            <Alert.Indicator />
                            <Alert.Description>
                                Google Client ID não configurado. Adicione{" "}
                                <strong>VITE_GOOGLE_CLIENT_ID</strong> no seu arquivo{" "}
                                <strong>.env</strong>.
                            </Alert.Description>
                        </Alert.Root>
                    ) : (
                        <LoginGoogleForm />
                    )}
                </Box>

                <Text fontSize="xs" color="fg.subtle" textAlign="center">
                    Ao fazer login, você concorda com nossos Termos de Serviço e Política de Privacidade.
                </Text>
            </Stack>
        </Center>
    );
}
