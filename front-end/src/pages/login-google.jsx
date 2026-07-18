import { useGoogleLogin } from "@react-oauth/google";
import { Center, Stack, Heading, Text, Button, Box, Alert } from "@chakra-ui/react";
import { FcGoogle } from "react-icons/fc";
import { useNavigate } from "react-router-dom";
import { loginWithGoogle } from "../api/endpoints";
import { saveToken } from "../lib/auth";

const hasClientId = Boolean(import.meta.env.VITE_GOOGLE_CLIENT_ID);

function LoginGoogleForm() {
    const navigate = useNavigate();

    const login = useGoogleLogin({
        onSuccess: async (tokenResponse) => {
            const data = await loginWithGoogle(tokenResponse.access_token);
            if (data?.data?.token) {
                saveToken(data.data.token);
                navigate("/");
            }
        },
        onError: () => {
            console.error("Google login failed");
        },
    });


    return (
        <Button
            id="google-login-btn"
            onClick={() => login()}
            variant="outline"
            w="full"
            size="lg"
            gap={3}
        >
            <FcGoogle size={22} />
            Continue with Google
        </Button>
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

