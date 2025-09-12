import { useState, useEffect } from "react"
import { Heading, Input, Center, Stack, Button, Text, Link } from "@chakra-ui/react";
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
                height="100vh"
                gap={6}
                width="35vh"
                align="center"
                justify="flex-start"
                pt={16}
            >
                <Heading size="2xl">
                    Welcome back!
                </Heading>

                <Input 
                placeholder="Email address" variant="outline"
                value={email} onChange={(e) => setEmail(e.target.value)}
                />

                <Input 
                placeholder="Password" variant="outline"
                value={password} onChange={(e) => setPassword(e.target.value)}
                />

                <Button onClick={handleSubmit}>
                    Log in
                </Button>

                <Link variant="underline" href="/create-account">
                    Don't have an account yet? Sign In now!
                </Link>
            </Stack>
        </Center>
    );
}