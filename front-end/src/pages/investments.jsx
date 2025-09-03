import { Stack, Center, Heading, Box } from "@chakra-ui/react"
import Home from "./home"

export default function Investments() {
    return(
        <Center>
            <Stack
                height="100vh"
                gap={6}
                width="35vh"
                align="center"
                justify="flex-start"
                pt={20}
            >
                <Heading size={"2xl"}>
                    Investments Dashboard
                </Heading>
                
            </Stack>
        </Center>
    )
}