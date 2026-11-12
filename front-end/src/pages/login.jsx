import { useState } from "react"
import { Heading, Input, Center, Stack, Button, Text, Link } from "@chakra-ui/react";
import { Link as RouterLink } from "react-router-dom";
import { loginUser } from "../api/endpoints";

export default function Login() {
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');

    const handleSubmit = () => {
        const userLoginInfo = {
            email: email,
            password: password
        };

        loginUser(userLoginInfo).then(data => {
            console.log("Successfully requested", data);
        })
    }

    return(
        <Center>
            <Stack
                minHeight="100dvh"
                gap={6}
                width="full"
                maxW="sm"
                px={6}
                align="center"
                justify="flex-start"
                pt={16}
            >
                <Heading size="2xl">
                    Bem-vindo de volta!
                </Heading>

                <Input 
                placeholder="Endereço de e-mail" variant="outline"
                value={email} onChange={(e) => setEmail(e.target.value)}
                />

                <Input 
                placeholder="Senha" variant="outline"
                value={password} onChange={(e) => setPassword(e.target.value)}
                />

                <Button onClick={handleSubmit}>
                    Entrar
                </Button>

                {/* The app's addresses start with "#": a plain href="/create-account" opens a page that does not exist */}
                <Link variant="underline" asChild>
                    <RouterLink to="/create-account">Ainda não tem uma conta? Crie uma agora!</RouterLink>
                </Link>
            </Stack>
        </Center>
    );
}