import { useState, useEffect } from "react"
import { Heading, Input, Center, Stack, Button, Text, Link } from "@chakra-ui/react";

export default function Login() {
    const [firstName, setFirstName] = useState('');
    const [lastName, setLastName] = useState('');
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');

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
                <Heading size="2xl">Welcome back!</Heading>

                <Input placeholder="Email address" variant="outline"/>
                <Input placeholder="Password" variant="outline"/>

                <Button>Log in</Button>

                <Link variant="underline" href="/create-account">Don't have an account yet? Sign In now!</Link>
            </Stack>
        </Center>
    );
}