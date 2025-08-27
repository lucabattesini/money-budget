import { Stack, Center, Heading } from "@chakra-ui/react"
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
                <Box position="absolute" right={6} top={6}>
                    <Home/>
                </Box>
                <Heading size={"2xl"}>
                    Investments Dashboard
                </Heading>
                
            </Stack>
        </Center>
    )
}