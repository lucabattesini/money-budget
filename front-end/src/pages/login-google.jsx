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
                    <Heading size="2xl">Welcome back!</Heading>
                    <Text color="fg.muted">Sign in to your account to continue</Text>
                </Stack>

                <Box w="full">
                    {!hasClientId ? (
                        <Alert.Root status="warning" borderRadius="lg">
                            <Alert.Indicator />
                            <Alert.Description>
                                Google Client ID not configured. Add{" "}
                                <strong>VITE_GOOGLE_CLIENT_ID</strong> to your{" "}
                                <strong>.env</strong> file.
                            </Alert.Description>
                        </Alert.Root>
                    ) : (
                        <LoginGoogleForm />
                    )}
                </Box>

                <Text fontSize="xs" color="fg.subtle" textAlign="center">
                    By signing in, you agree to our Terms of Service and Privacy Policy.
                </Text>
            </Stack>
        </Center>
    );
}
